import json
import re
import urllib.parse
import zlib

import pymongo

##### ##### ##### ##### #####

# Regular expression to match the URL pattern for channel messages
CHANNELS_ID_MESSAGES_REGEX = re.compile(r"^/api/v9/channels/(\d+)/messages$")

##### ##### ##### ##### #####

# Create a MongoDB client
client = pymongo.MongoClient()

# Create a dictionary to store the buffers for each WebSocket connection
buffers = {}

# Create a dictionary to store the decompressor objects for each WebSocket connection
decompressors = {}

##### ##### ##### ##### #####

def response(flow):
  # Parse the URL of the request
  url = urllib.parse.urlparse(flow.request.url)

  # Check if the URL path matches the pattern for channel messages
  if url.hostname == "discord.com" and (match := CHANNELS_ID_MESSAGES_REGEX.match(url.path)):
    # If the response status code is not 200
    if flow.response.status_code != 200:
      # Return to avoid writing the messages
      return

    # If it's a GET request
    if flow.request.method == "GET":
      # Load the messages from the response content
      messages = json.loads(flow.response.content)

      # Create a list of operations for bulk writing to MongoDB
      operations = []

      # Process each message
      for message in messages:
        # Convert the message ID to an int and store it
        message["_id"] = int(message["id"])

        # Add a ReplaceOne operation to the list of operations
        operations.append(pymongo.ReplaceOne({"_id": message["_id"]}, message, upsert=True))

      # If there are any operations to perform
      if len(operations) > 0:
        # Perform the bulk write operation to MongoDB
        result = client["discorddump"]["messages"].bulk_write(operations, ordered=False)

        # Log the number of messages saved for the channel
        print(f"Saved {len(operations) - result.matched_count}/{len(operations)} messages from channel {match.group(1)}")

    # If it's a POST request
    if flow.request.method == "POST":
      # Load the message from the response content
      message = json.loads(flow.response.content)

      # Convert the message ID to an int and store it
      message["_id"] = int(message["id"])

      # If the nonce field is present
      if "nonce" in message:
        # Remove it from the message
        del message["nonce"]

      # Insert the message to MongoDB
      client["discorddump"]["messages"].replace_one({"_id": message["_id"]}, message, upsert=True)

      # Log the number of messages saved for the channel
      print(f"Saved 1 messages from channel {match.group(1)}")

  if url.hostname == "discord.com" and url.path == "/api/v9/users/@me/channels" and flow.request.method == "POST":
    # Load the channel data from the response content
    response = flow.response.json()

    # Create a channel object with the relevant fields from the response data
    channel_obj = {
      "_id": int(response["id"]),
      "type": response["type"],
      "safety_warnings": [],
      "recipient_ids": [recipient["id"] for recipient in response["recipients"]],
      "recipient_flags": 0,
      "last_pin_timestamp": response["last_pin_timestamp"] if "last_pin_timestamp" in response else None,
      "last_message_id": response["last_message_id"] if "last_message_id" in response else None,
      "is_spam": False,
      "is_message_request_timestamp": None,
      "is_message_request": False,
      "id": response["id"],
      "flags": response["flags"],
    }

    # If the last_pin_timestamp field is None
    if channel_obj["last_pin_timestamp"] is None:
      # Remove the last_pin_timestamp field from the channel data
      del channel_obj["last_pin_timestamp"]

    # If the last_message_id field is None
    if channel_obj["last_message_id"] is None:
      # Remove the last_message_id field from the channel data
      del channel_obj["last_message_id"]

    # Insert the channel to MongoDB
    client["discorddump"]["channels"].replace_one({"_id": channel_obj["_id"]}, channel_obj, upsert=True)

    # Log the number of channels saved
    print(f"Saved 1 channel")

    # Create a list of operations for bulk writing to MongoDB
    user_operations = []

    # Iterate through the recipients of the channel
    for recipient in response["recipients"]:
      # Create a user object with the relevant fields from the recipient data
      user_obj = {
        "_id": int(recipient["id"]),
        "username": recipient["username"],
        "public_flags": recipient["public_flags"],
        "primary_guild": recipient["primary_guild"],
        "id": recipient["id"],
        "global_name": recipient["global_name"],
        "display_name_styles": recipient["display_name_styles"],
        "discriminator": recipient["discriminator"],
        "collectibles": recipient["collectibles"],
        "clan": recipient["clan"],
        "bot": recipient["bot"] if "bot" in recipient else None,
        "avatar_decoration_data": recipient["avatar_decoration_data"],
        "avatar": recipient["avatar"],
      }

      # If the bot field is not present in the recipient data
      if user_obj["bot"] is None:
        # Remove the bot field from the user data
        del user_obj["bot"]

      # Add a ReplaceOne operation to the list of operations
      user_operations.append(pymongo.ReplaceOne({"_id": user_obj["_id"]}, user_obj, upsert=True))

    # If there are any operations to perform
    if len(user_operations) > 0:
      # Perform the bulk write operation to MongoDB
      result = client["discorddump"]["users"].bulk_write(user_operations, ordered=False)

      # Log the number of messages saved for the channel
      print(f"Saved {len(user_operations) - result.matched_count}/{len(user_operations)} users")

def websocket_start(flow):
  # Parse the URL of the request
  url = urllib.parse.urlparse(flow.request.url)

  # Check if the URL path matches the pattern for Discord Gateway WebSocket connections
  if url.hostname.startswith("gateway") and url.hostname.endswith(".discord.gg") and "encoding=json" in url.query and "compress=zlib-stream" in url.query:
    # Initialize the buffer for the WebSocket connection
    buffers[flow.id] = bytearray()

    # Initialize the decompressor for the WebSocket connection
    decompressors[flow.id] = zlib.decompressobj()

def gateway_message(message):
  """
  import time
  with open(f"data/gateway/{time.time_ns()}.json", "w") as f:
    json.dump(message, f, indent=2)
  """

  # If the message is an operation with code 0 (dispatch)
  if message["op"] == 0:
    # If the message is an event with the name "READY"
    if message["t"] == "READY":
      # Create a list of operations for bulk writing to MongoDB
      guild_operations = []
      channel_operations = []
      user_operations = []

      # Iterate through the guilds
      for guild in message["d"]["guilds"]:
        # Convert the guild ID to an int and store it
        guild["properties"]["_id"] = int(guild["properties"]["id"])

        # Populate the properties field of the guild data with the corresponding fields from the guild data
        guild["properties"]["emojis"] = guild["emojis"]
        guild["properties"]["roles"] = guild["roles"]
        guild["properties"]["stickers"] = guild["stickers"]

        # Add the missing fields with default values to the guild data
        guild["properties"]["embed_enabled"] = False
        guild["properties"]["embed_channel_id"] = None
        guild["properties"]["inventory_settings"] = None
        guild["properties"]["max_members"] = 25000000
        guild["properties"]["max_presences"] = None
        guild["properties"]["premium_subscription_count"] = 0
        guild["properties"]["region"] = "eu-central"
        guild["properties"]["widget_channel_id"] = None
        guild["properties"]["widget_enabled"] = False

        # Remove the unnecessary fields from the guild data
        del guild["properties"]["moderator_reporting"]
        del guild["properties"]["premium_features"]
        del guild["properties"]["profile"]

        # Add a ReplaceOne operation to the list of operations
        guild_operations.append(pymongo.ReplaceOne({"_id": guild["properties"]["_id"]}, guild["properties"], upsert=True))

        # Iterate through the channels in the guild
        for channel in guild["channels"]:
          # Convert the channel ID to an int and store it
          channel["_id"] = int(channel["id"])

          # Add the guild ID to the channel data
          channel["guild_id"] = guild["id"]

          # If the nsfw field is not present in the channel data
          if "nsfw" not in channel:
            # Assume the channel is not NSFW and set the field to False
            channel["nsfw"] = False

          # Add a ReplaceOne operation to the list of operations
          channel_operations.append(pymongo.ReplaceOne({"_id": channel["_id"]}, channel, upsert=True))

      # Iterate through the private channels
      for channel in message["d"]["private_channels"]:
        # Convert the channel ID to an int and store it
        channel["_id"] = int(channel["id"])

        # Add a ReplaceOne operation to the list of operations
        channel_operations.append(pymongo.ReplaceOne({"_id": channel["_id"]}, channel, upsert=True))

      for user in message["d"]["users"]:
        # Convert the user ID to an int and store it
        user["_id"] = int(user["id"])

        # Add a ReplaceOne operation to the list of operations
        user_operations.append(pymongo.ReplaceOne({"_id": user["_id"]}, user, upsert=True))

      # If there are any operations to perform
      if len(guild_operations) > 0:
        # Perform the bulk write operation to MongoDB
        result = client["discorddump"]["guilds"].bulk_write(guild_operations, ordered=False)

        # Log the number of guilds saved
        print(f"Saved {len(guild_operations) - result.matched_count}/{len(guild_operations)} guilds")

      # If there are any operations to perform
      if len(channel_operations) > 0:
        # Perform the bulk write operation to MongoDB
        result = client["discorddump"]["channels"].bulk_write(channel_operations, ordered=False)

        # Log the number of channels saved for the guilds
        print(f"Saved {len(channel_operations) - result.matched_count}/{len(channel_operations)} channels from {len(message['d']['guilds'])} guilds and {len(message['d']['private_channels'])} private channels")

      # If there are any operations to perform
      if len(user_operations) > 0:
        # Perform the bulk write operation to MongoDB
        result = client["discorddump"]["users"].bulk_write(user_operations, ordered=False)

        # Log the number of users saved
        print(f"Saved {len(user_operations) - result.matched_count}/{len(user_operations)} users")

    # If the message is an event with the name "MESSAGE_CREATE"
    if message["t"] == "MESSAGE_CREATE":
      # Convert the message ID to an int and store it
      message["d"]["_id"] = int(message["d"]["id"])

      # Remove the unnecessary fields from the message
      for field in ["guild_id", "nonce", "member"]:
        # If the field is present in the message data
        if field in message["d"]:
          # Remove it from the message data
          del message["d"][field]

      # Insert the message to MongoDB
      client["discorddump"]["messages"].replace_one({"_id": message["d"]["_id"]}, message["d"], upsert=True)

      # Log the number of messages saved for the channel
      print(f"Saved 1 messages from channel {message['d']['channel_id']}")

def websocket_message(flow):
  # If the WebSocket message is from the client
  if flow.websocket.messages[-1].from_client:
    # Skip processing the WebSocket message
    return

  # If there is no buffer or decompressor for the WebSocket connection
  if not flow.id in buffers.keys() or not flow.id in decompressors.keys():
    # Skip processing the WebSocket message
    return

  # Get the content of the last WebSocket message
  data = flow.websocket.messages[-1].content

  # Append the WebSocket data to the buffer for the connection
  buffers[flow.id].extend(data)

  # If the last 4 bytes of the buffer are not the zlib stream terminator
  if len(data) < 4 or data[-4:] != b'\x00\x00\xff\xff':
    # Skip processing the WebSocket message
    return
  
  # Decompress the buffer for the WebSocket connection and store it in msg
  message = decompressors[flow.id].decompress(buffers[flow.id])

  # Parse the message as JSON
  message = json.loads(message)

  # Try to process the message
  try:
    # Process the message
    gateway_message(message)
  except Exception as e:
    # Log any error that occurs while processing the message
    print(f"Error processing gateway message")
    print(e)

  # Reset the buffer for the WebSocket connection
  buffers[flow.id] = bytearray()

def websocket_end(flow):
  # If there are buffer for the WebSocket connection
  if buffers.get(flow.id):
    # Delete it
    del buffers[flow.id]

  # If there are decompressor for the WebSocket connection
  if decompressors.get(flow.id):
    # Delete it
    del decompressors[flow.id]
