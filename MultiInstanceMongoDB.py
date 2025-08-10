"""
MongoDB Command Filter Plugin for Errbot
This plugin uses MongoDB to filter commands across multiple instances of Errbot.
It ensures that only the first instance that receives a command will execute it,
while later instances will assume the command has already been executed.
"""
import uuid
from datetime import datetime
from datetime import timezone

from errbot import botcmd
from errbot import BotPlugin
from errbot import cmdfilter
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo.uri_parser import parse_uri

MONGODB_URI = "BOT_MULTI_INSTANCE_MONGODB_URI"
MONGODB_INDEX_TTL = "BOT_MULTI_INSTANCE_INDEX_TTL"
INDEX_NAME = "datetime_ttl"


class MultiInstanceMongoDBPlugin(BotPlugin):
    def __init__(self, bot, name=None):
        super().__init__(bot, name)
        self.mongo_client = None
        self.collection = None
        self.instance_id = str(uuid.uuid4())

    def activate(self):
        super().activate()

        mongo_uri =  getattr(self.bot_config, MONGODB_URI, None)
        if not mongo_uri:
            raise ValueError(
                    f"{MONGODB_URI} must be set in the bot configuration."
            )

        parsed = parse_uri(mongo_uri)
        collection = parsed.get("collection")

        ttl = getattr(self.bot_config, MONGODB_INDEX_TTL, 60)

        if not collection:
            raise ValueError(
                    f"{MONGODB_URI} must specify both database and collection, e.g. /<db>.<collection>"
            )

        self.mongo_client = MongoClient(mongo_uri)
        db = self.mongo_client.get_database()
        if collection not in db.list_collection_names():
            self.collection = db.create_collection(collection)
        else:
            self.collection = db[collection]

        for idx in self.collection.list_indexes():
            if idx.get('name') == INDEX_NAME:
                if idx.get('expireAfterSeconds') != ttl:
                    self.collection.drop_index(INDEX_NAME)
                    self.collection.create_index("datetime", expireAfterSeconds=ttl, name=INDEX_NAME)
                break
        else:
            self.collection.create_index("datetime", expireAfterSeconds=ttl, name=INDEX_NAME)


    def deactivate(self):
        """
        Deactivate the plugin, removing the command filter and closing the MongoDB connection.
        """
        self.mongo_client.close()
        super().deactivate()

    @cmdfilter
    def mongodb_cmd_filter(self, msg, cmd, args, dry_run):
        """
        Command filter that determines whether to allow a command to proceed.

        If this instance is able to store the command in MongoDB, this instance
        must be first and will be entitled to execute the command. Any later
        instances will hit a duplicate key error and as a result will assume that
        the command has been executed by the first instance.
        """
        if not dry_run:

            flow, _ = self._bot.flow_executor.check_inflight_flow_triggered(cmd, msg.frm)
            message_id = msg.extras.get("message_id") or f"{msg.body}|{msg.frm}|{msg.to}|{cmd}|{args}".encode("utf-8")

            if not flow:
                try:
                    self.collection.insert_one(
                            {
                                "_id"        : message_id,
                                "instance_id": self.instance_id,
                                "datetime"   : datetime.now(timezone.utc),
                            }
                    )

                except DuplicateKeyError:
                    return None, None, None

                return msg, cmd, args


            result = self.collection.update_one(
                {"$and": [
                    {
                        "flow_name" : flow.name,
                        "message_id": message_id,
                    },
                    {"$or": [
                        {"instance_id": self.instance_id},
                        {"instance_id": {"$exists": False}}
                    ]}
                ]},
                    {
                        "$setOnInsert": {
                            "instance_id": self.instance_id,
                            "datetime"   : datetime.now(timezone.utc),
                        }
                    },
                upsert=True
            )

            if result.matched_count == 0 and result.upserted_id is None:
                return None, None, None

        return msg, cmd, args

    @botcmd
    def show_instance_id(self, _msg, _args):
        """
        Display the unique instance ID for this plugin instance.
        """
        return f"Instance ID: {self.instance_id}"
