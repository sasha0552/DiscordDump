# read data/all_messageids.json and verify message ids in mongodb

import json
import os

import pymongo

def main():
  # Create a MongoDB client
  client = pymongo.MongoClient()

  # Get the messages collection count
  messages = client["discorddump"]["messages"]

  # Load the message IDs from the JSON file
  with open("data/all_messageids.json", "r") as f:
    message_ids = set(json.load(f))
  
  # convert ids to str
  message_ids = set(str(id) for id in message_ids)

  # Initialize a set to store the message IDs that is present
  found = set()

  # Iterate through the messages in batches
  for message in messages.find({}, {"id": 1}, batch_size=1000):
    # Get the message ID from the message
    message_id = message["id"]

    # If the message ID is not in the set of message IDs from the JSON file
    if message_id in message_ids:
      # Add the message ID to the set of invalid message IDs
      found.add(message_id)

  # Print the number of valid and invalid message IDs
  print(f"Found {len(found)} valid message IDs out of {len(message_ids)} total message IDs")

if __name__ == "__main__":
  main()
