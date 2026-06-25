import uuid
import decimal
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header
from mangum import Mangum
from pydantic import BaseModel, Field
from typing import List, Optional
from app.dynamodb_storage import DynamoDBRepository
from app.s3_storage import S3FileRepository

app = FastAPI(
    title="Freight bidding workflow orchestrator",
    description="Automated competitive freight bidding API",
    version="1.0.0"
)

# Instantiate database and file storage repositories
db = DynamoDBRepository()
s3 = S3FileRepository()

# --- Pydantic Schemas ---

class CustomerResponse(BaseModel):
    id: int
    name: str
    email: str
    default_markup_percent: float = 10.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FreightQuoteCreate(BaseModel):
    customer_id: int
    origin: str
    destination: str
    weight_lbs: float
    pickup_date: datetime
    dimensions: Optional[str] = "48x48x48"
    freight_class: Optional[str] = "70"
    hazmat: Optional[bool] = False
    accessorials: Optional[str] = ""

class FreightQuoteResponse(BaseModel):
    id: str
    customer_id: int
    customer: CustomerResponse
    status: str = "Draft"
    origin: str
    destination: str
    weight_lbs: float
    dimensions: Optional[str] = None
    freight_class: Optional[str] = None
    hazmat: bool = False
    accessorials: Optional[str] = None
    pickup_date: datetime
    first_round_ends_at: Optional[datetime] = None
    rebid_round_ends_at: Optional[datetime] = None
    quote_expires_at: Optional[datetime] = None
    cost_price: float = 0.0
    sell_price: float = 0.0
    markup_percent: float = 10.0
    margin_amt: float = 0.0
    margin_pct: float = 0.0
    winning_carrier_id: Optional[int] = None
    winning_carrier: Optional[dict] = None
    lost_reason: Optional[str] = None
    competitor_info: Optional[str] = None
    payment_status: str = "Pending"
    bol_url: Optional[str] = None
    invoice_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    bids: List[dict] = []
    transitions: List[dict] = []
    rfqs: List[dict] = []

class PresignedUrlResponse(BaseModel):
    upload_url: str
    file_key: str
    asset_url: str

# --- Routes ---

@app.get("/")
def read_root():
    """
    Root endpoint verifying API is running.
    """
    return {
        "title": app.title,
        "version": app.version,
        "status": "online",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/quotes", response_model=FreightQuoteResponse)
def create_quote(quote_in: FreightQuoteCreate, x_user_email: str = Header(..., alias="X-User-Email")):
    """
    Creates a new freight quote and saves it to DynamoDB.
    """
    # Create a mock customer for the response
    mock_customer = CustomerResponse(
        id=quote_in.customer_id,
        name=x_user_email.split("@")[0].capitalize(),
        email=x_user_email
    )
    
    # Initialize the quote response object
    quote_id = str(uuid.uuid4())
    quote_data = FreightQuoteResponse(
        id=quote_id,
        customer_id=quote_in.customer_id,
        customer=mock_customer,
        origin=quote_in.origin,
        destination=quote_in.destination,
        weight_lbs=quote_in.weight_lbs,
        dimensions=quote_in.dimensions,
        freight_class=quote_in.freight_class,
        hazmat=quote_in.hazmat or False,
        accessorials=quote_in.accessorials,
        pickup_date=quote_in.pickup_date,
    )
    
    # Convert Pydantic object to dictionary
    try:
        data_to_save = quote_data.model_dump()
    except AttributeError:
        data_to_save = quote_data.dict()
        
    # Serialize datetime objects to ISO strings for DynamoDB compatibility
    # DynamoDB does not support native datetime objects
    serialized_data = json_datetime_serializer(data_to_save)
    
    # Save to DynamoDB Single Table
    db.save_item(pk="QUOTES", sk=f"QUOTE#{quote_id}", data=serialized_data)
    return quote_data

@app.get("/api/quotes", response_model=List[FreightQuoteResponse])
def get_quotes(x_user_email: str = Header(..., alias="X-User-Email")):
    """
    Lists all quotes stored in DynamoDB.
    """
    quotes = db.list_items(pk="QUOTES", sk_prefix="QUOTE#")
    return quotes

@app.get("/api/quotes/{quote_id}", response_model=FreightQuoteResponse)
def get_quote(quote_id: str, x_user_email: str = Header(..., alias="X-User-Email")):
    """
    Retrieves a single quote by ID from DynamoDB.
    """
    quote = db.get_item(pk="QUOTES", sk=f"QUOTE#{quote_id}")
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote with ID {quote_id} not found")
    return quote

@app.post("/api/quotes/{quote_id}/upload-url", response_model=PresignedUrlResponse)
def get_presigned_upload_url(
    quote_id: str, 
    filename: str, 
    x_user_email: str = Header(..., alias="X-User-Email")
):
    """
    Generates a secure pre-signed S3 URL to upload a file (e.g. cargo image, BOL PDF) for a quote.
    Clients upload files directly from their browser/app to S3 using the upload_url.
    """
    # Verify that the quote exists first
    quote = db.get_item(pk="QUOTES", sk=f"QUOTE#{quote_id}")
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote with ID {quote_id} not found")

    file_key = f"quotes/{quote_id}/{filename}"
    upload_url = s3.generate_presigned_url(file_key=file_key, method="put_object")
    
    if upload_url is None:
        raise HTTPException(status_code=500, detail="Failed to generate secure upload URL")
        
    asset_url = f"https://{s3.bucket_name}.s3.amazonaws.com/{file_key}"
    
    return PresignedUrlResponse(
        upload_url=upload_url,
        file_key=file_key,
        asset_url=asset_url
    )

# --- Helper Functions ---

def json_datetime_serializer(obj: any) -> any:
    """
    Recursively formats datetimes to ISO strings and floats to Decimals for DynamoDB compatibility.
    """
    if isinstance(obj, dict):
        return {k: json_datetime_serializer(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_datetime_serializer(x) for x in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, float):
        return decimal.Decimal(str(obj))
    return obj

# Mangum handler for AWS Lambda API Gateway integration
handler = Mangum(app)
