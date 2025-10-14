from typing import Dict,Any,List
from db.db_connection import get_connection
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self,client: AsyncIOMotorClient, db_name: str):
        self.client = client
        self.db = client[db_name]
        
    async def find_one(self, collection:str, filter_dict:Dict[str,Any]):
        try:
            result = await self.db[collection].find_one(filter_dict)
            return result
        except Exception as e:
            logger.error(f'Error finding data in {collection}: {e}')
            raise 

    async def find_many(self, collection:str, filter_dict: Dict[str,Any] = None, skip: int = 0, limit:int = 0, sort:List = None):
        try:
            cursor = self.db[collection].find(filter_dict or {})
            if sort:
                cursor = cursor.sort(sort)
            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)
            
            result = await cursor.to_list(length = None)
            return result
        except Exception as e:
            raise e

    async def insert_one(self, collection:str, document: Dict[str,Any]):
        try:
            result = await self.db[collection].insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            raise e
    
    async def update_one(self, collection: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        try:
            if any(key.startswith('$') for key in update_dict.keys()):
                result = await self.db[collection].update_one(filter_dict, update_dict)
            else:
                result = await self.db[collection].update_one(filter_dict, {"$set": update_dict})
            return result.modified_count > 0
        except Exception as e:
            raise e
    
    async def update_many(self, collection: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        try:
            if any(key.startswith('$') for key in update_dict.keys()):
                result = await self.db[collection].update_many(filter_dict, update_dict)
            else:
                result = await self.db[collection].update_many(filter_dict, {"$set": update_dict})
            return result.modified_count > 0
        except Exception as e:
            raise e

    async def count_documents(self,collection:str,filter_dict:Dict[str,Any] = None):
        try:
            return await self.db[collection].count_documents(filter_dict or {})
        except Exception as e:
            raise e
    
    async def delete_one(self, collection:str, filter_dict:Dict[str,Any]):
        try:
            result = await self.db[collection].delete_one(filter_dict)
            return result.deleted_count
        except Exception as e:
            raise e

    async def aggregate(self,collection:str, pipeline:List[Dict[str,Any]]):
        try:
            cursor = self.db[collection].aggregate(pipeline)
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error performing aggregation: {e}")
            raise

def get_database():
    client = get_connection()
    return DatabaseManager(client,os.getenv('DB_NAME'))