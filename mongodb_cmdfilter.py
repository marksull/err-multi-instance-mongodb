"""
MongoDB Command Filter Plugin for Errbot
This plugin uses MongoDB to filter commands across multiple instances of Errbot.
It ensures that only the first instance that receives a command will execute it,
while later instances will assume the command has already been executed.
"""
import uuid
import zlib

from errbot import botcmd
from errbot import BotPlugin
from errbot import cmdfilter
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri

ENV_VAR_MONGODB_URI = "MULTI_INSTANCE_MONGODB_URI"


class MongoDBCmdFilterPlugin(BotPlugin):
    def __init__(self, bot_config):
        super().__init__(bot_config)
        self.mongo_client = None
        self.collection = None
        self.instance_id = str(uuid.uuid4())

    def activate(self):
        super().activate()

        mongo_uri = self.bot_config.MONGODB_URI

        if not mongo_uri:
            raise ValueError(
                f"{ENV_VAR_MONGODB_URI} must be set in the bot configuration."
            )

        parsed = parse_uri(mongo_uri)
        collection = parsed.get("collection")

        if not collection:
            raise ValueError(
                f"{ENV_VAR_MONGODB_URI} must specify both database and collection, e.g. /<db>.<collection>"
            )

        self.mongo_client = MongoClient(mongo_uri)
        self.collection = self.mongo_client.get_database()[collection]

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
        try:
            if not dry_run:
                self.collection.insert_one(
                    {
                        "_id": zlib.crc32(
                            f"{msg.body}|{msg.frm}|{msg.to}|{cmd}|{args}".encode(
                                "utf-8"
                            )
                        ),
                        "flow": msg.flow.name if msg.flow else None,
                        "instance_id": self.instance_id,
                    }
                )
        except self.mongo_client.errors.DuplicateKeyError:
            return None, None, None

        return cmd, args, dry_run

    @botcmd
    def show_instance_id(self, _msg, _args):
        """
        Display the unique instance ID for this plugin instance.
        """
        return f"Instance ID: {self.instance_id}"
