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
MONGODB_INDEX_FLOW_TTL = "BOT_MULTI_INSTANCE_INDEX_FLOW_TTL"
INDEX_NAME = "datetime_ttl"
INDEX_NAME_FLOW = "datetime_flow_ttl"


class MultiInstanceMongoDBPlugin(BotPlugin):
    def __init__(self, bot, name=None):
        super().__init__(bot, name)
        self.mongo_client = None
        self.collection = None
        self.instance_id = str(uuid.uuid4())

    def activate(self):
        super().activate()

        mongo_uri = getattr(self.bot_config, MONGODB_URI, None)
        if not mongo_uri:
            raise ValueError(f"{MONGODB_URI} must be set in the bot configuration.")

        parsed = parse_uri(mongo_uri)
        collection = parsed.get("collection")

        ttl = getattr(self.bot_config, MONGODB_INDEX_TTL, 30)
        ttl_flow = getattr(self.bot_config, MONGODB_INDEX_FLOW_TTL, 60 * 5)

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
            if idx.get("name") == INDEX_NAME:
                if idx.get("expireAfterSeconds") != ttl:
                    self.collection.drop_index(INDEX_NAME)
                    self.collection.create_index(
                        "datetime", expireAfterSeconds=ttl, name=INDEX_NAME
                    )
                break
        else:
            self.collection.create_index(
                "datetime", expireAfterSeconds=ttl, name=INDEX_NAME
            )

        for idx in self.collection.list_indexes():
            if idx.get("name") == INDEX_NAME_FLOW:
                if idx.get("expireAfterSeconds") != ttl_flow:
                    self.collection.drop_index(INDEX_NAME_FLOW)
                    self.collection.create_index(
                        "datetime_flow",
                        expireAfterSeconds=ttl_flow,
                        name=INDEX_NAME_FLOW,
                    )
                break
        else:
            self.collection.create_index(
                "datetime_flow", expireAfterSeconds=ttl_flow, name=INDEX_NAME_FLOW
            )

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
        if dry_run:
            return msg, cmd, args

        flow_root = None

        # If the backend injects the message id into the "extras" dict, we will
        # use it to differentiate the command, else we will create a key
        # based on the message body, sender, recipient, command and arguments.
        # Because the message contains no timing or message-specific uniqueness,
        # if a user repeats the same command before the TTL has expired, it
        # will be considered to be the same command and will not be executed again.
        # To avoid this, the backend should inject a unique message id into the
        # "extras" dict of the message.
        message_id = msg.extras.get(
            "message_id"
        ) or f"{msg.body}|{msg.frm}|{msg.to}|{cmd}|{args}".encode("utf-8")

        # The flow is only attached to a message AFTER the flow has progressed
        # past the filtering. So we need to do some pre-checks to determine if
        # the command will trigger a new flow or is part of an existing flow
        flow_inflight, _ = self._bot.flow_executor.check_inflight_flow_triggered(
            cmd, msg.frm
        )

        if flow_inflight:
            flow_root = flow_inflight.flow_root

        if not flow_root:
            # is the command going to trigger a new flow?
            flow_root = cmd in self._bot.flow_executor.flow_roots

        if flow_root:

            flow_find = self.collection.find_one({"flow_root": flow_root})

            if flow_find:
                if flow_find.get("instance_id") == self.instance_id:
                    # this instance owns the flow to we should run with it
                    return msg, cmd, args
                else:
                    # another instance has already started with the flow, so we should not run with it
                    return None, None, None

            try:
                self.collection.insert_one(
                    {
                        "_id": message_id,
                        "instance_id": self.instance_id,
                        "flow_root": flow_root,
                        "datetime_flow": datetime.now(timezone.utc),
                    }
                )
                return msg, cmd, args

            except DuplicateKeyError:
                return None, None, None

        try:
            self.collection.insert_one(
                {
                    "_id": message_id,
                    "instance_id": self.instance_id,
                    "datetime": datetime.now(timezone.utc),
                }
            )

        except DuplicateKeyError:
            return None, None, None

        return msg, cmd, args

    @botcmd
    def show_instance_id(self, _msg, _args):
        """
        Display the unique instance ID for this plugin instance.
        """
        return f"Instance ID: {self.instance_id}"
