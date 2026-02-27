import json
import os
import re
import sys
import urllib.parse

import pymongo

def find_values_by_criteria(object, criteria_fn):
  if isinstance(object, dict):
    # Iterate through the values in the object
    for value in object.values():
      # Recursively call the function on the value and yield the results
      yield from find_values_by_criteria(value, criteria_fn)
  elif isinstance(object, list):
    # Iterate through the items in the list
    for item in object:
      # Recursively call the function on the item and yield the results
      yield from find_values_by_criteria(item, criteria_fn)
  else:
    # If the object matches the criteria
    if criteria_fn(object):
      # Yield the object
      yield object

def main():
  # Create a MongoDB client
  client = pymongo.MongoClient()

  # Get the messages collection count
  messages = client["discorddump"]["messages"]

  # Initialize the attachments counters
  attachments = 0
  valid_attachments = 0

  # Initialize a set to store the attachment URLs that have been checked
  checked = set()

  # Iterate through the messages in batches
  for message in messages.find({}, {}, batch_size=1000):
    # Create an object with the attachments, embeds, and components fields from the message
    object = {
      "attachments": message.get("attachments", []),
      "embeds": message.get("embeds", []),
      "components": message.get("components", []),
    }

    # Define a criteria function to check if a value is a string that starts with the URL pattern for attachments
    criteria = lambda value: isinstance(value, str) and str(value).startswith("https://cdn.discordapp.com/attachments/") or str(value).startswith("https://media.discordapp.net/attachments/")

    # Iterate through the values in the message that match the criteria
    for attachment in find_values_by_criteria(object, criteria):
      # Parse the URL of the request
      url = urllib.parse.urlparse(attachment)

      # Get the clean URL without query parameters
      attachment_url = url._replace(netloc="cdn.discordapp.com", query="").geturl()

      # If the attachment URL has not been checked yet
      if attachment_url not in checked:
        # Increment the attachments count
        attachments += 1

        # Check if the URL path matches the pattern for attachments                      
        if (match := re.match(r"^/attachments/(\d+)/(\d+)/([^/]+)$", url.path)):
          # If the file for the attachment does not exist
          if not os.path.exists(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3))):
            # Print the channel ID and the attachment URL
            print(f"Message ID: {message['id']}, attachment doesn't exist {attachment_url}", file=sys.stderr)
          else:
            if os.path.getsize(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3))) == 0:
              # Print the channel ID and the attachment URL
              print(f"Message ID: {message['id']}, attachment is empty {attachment_url}", file=sys.stderr)
            else:
              # Increment the valid attachments count
              valid_attachments += 1
        else:
          # Print the channel ID and the attachment URL
          print(f"Message ID: {message['id']}, attachment URL doesn't match the pattern {attachment_url}", file=sys.stderr)

      # Add the attachment URL to the set of checked URLs
      checked.add(attachment_url)

  print("===== ===== ===== ===== =====")
  print(f"Total messages: {messages.count_documents({})}")
  print(f"Unique users: {len(client['discorddump']['users'].distinct('id'))}/{len(messages.distinct('author.id'))}")
  print(f"Attachments: {valid_attachments}/{attachments}")
  print("===== ===== ===== ===== =====")
  print("")

if __name__ == "__main__":
  main()
