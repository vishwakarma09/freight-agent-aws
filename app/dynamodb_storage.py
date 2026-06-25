import os
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class DynamoDBRepository:
    """
    A single-table DynamoDB repository wrapping boto3 operations.
    Supports basic key-value operations and partition queries.
    """
    def __init__(self, table_name: Optional[str] = None):
        self.table_name = table_name or os.environ.get("DYNAMODB_TABLE", "freight-agent-api-dev-data")
        self.db = boto3.resource("dynamodb")
        self.table = self.db.Table(self.table_name)

    def save_item(self, pk: str, sk: str, data: Dict[str, Any]) -> bool:
        """
        Saves a dictionary as an item in the DynamoDB table.
        Adds the PK and SK partition/sort keys to the item.
        """
        item = {**data, "PK": pk, "SK": sk}
        try:
            self.table.put_item(Item=item)
            logger.info(f"Successfully saved item with PK={pk}, SK={sk}")
            return True
        except ClientError as e:
            logger.error(f"Failed to save item PK={pk}, SK={sk}: {e}")
            raise e

    def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single item from the DynamoDB table.
        Returns None if not found.
        """
        try:
            response = self.table.get_item(Key={"PK": pk, "SK": sk})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to retrieve item PK={pk}, SK={sk}: {e}")
            raise e

    def delete_item(self, pk: str, sk: str) -> bool:
        """
        Deletes a single item from the DynamoDB table.
        """
        try:
            self.table.delete_item(Key={"PK": pk, "SK": sk})
            logger.info(f"Successfully deleted item PK={pk}, SK={sk}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete item PK={pk}, SK={sk}: {e}")
            raise e

    def list_items(self, pk: str, sk_prefix: str = "") -> List[Dict[str, Any]]:
        """
        Lists items in a partition matching a sort key prefix.
        E.g., list_items(pk="QUOTES", sk_prefix="QUOTE#")
        """
        try:
            # Query DynamoDB table
            if sk_prefix:
                response = self.table.query(
                    KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                    ExpressionAttributeValues={
                        ":pk": pk,
                        ":sk_prefix": sk_prefix
                    }
                )
            else:
                response = self.table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={
                        ":pk": pk
                    }
                )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Failed to query items PK={pk}, sk_prefix={sk_prefix}: {e}")
            raise e
