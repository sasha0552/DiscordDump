import concurrent.futures
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse

import pymongo
import requests
import tqdm

##### ##### ##### ##### #####

# Create a thread pool executor to download attachments concurrently
executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)

# Create a lock to synchronize access to the set of downloading files
download_lock = threading.Lock()

# Create a set to keep track of the files that are currently being downloaded
downloading_files = set()

##### ##### ##### ##### #####

def download(url, path):
  # Acquire the lock
  with download_lock:
    # If the file is already being downloaded
    if path in downloading_files:
      # Return to avoid downloading the same file multiple times
      return

    # Add the file to the set of downloading files
    downloading_files.add(path)

  try:
    # Download the file using the URL
    with requests.get(url, stream=True) as response:
      # Throw exception if the response status code is not 200
      response.raise_for_status()

      # Open a file to write the content
      with open(path, "wb") as file:
        # Write the content to the file in chunks
        for chunk in response.iter_content(chunk_size=8192): 
          # Write the chunk to the file
          file.write(chunk)

      # Print a message indicating that the file has been downloaded
      tqdm.tqdm.write(f"Downloaded {url.split('?')[0]}")
  except Exception as e:
    # Print the error message
    tqdm.tqdm.write(f"Error downloading {url}: {e}")
  finally:
    # Acquire the lock
    with download_lock:
      # Remove the file from the set of downloading files
      downloading_files.remove(path)

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

##### ##### ##### ##### #####

def main():
  # Create a MongoDB client
  client = pymongo.MongoClient()

  # Current token index for rotating through multiple tokens if needed
  current_token = 0

  # List to store guild IDs and their priorities
  guilds = []

  # Read the token from the .env file
  with open(".env", "r") as file:
    tokens = [line.split("=")[1].strip() for line in file if line.startswith("DISCORD_TOKEN")]

  # Read the guild IDs from the guilds.txt file
  with open("./guilds.txt", "r") as file:
    # file format: guild_id : proirity. strip them
    for line in file:
      # Skip comments and empty lines
      if line.startswith("#") or not line.strip():
        # Continue to the next line
        continue

      # Split the line into guild ID and priority
      guild_id, priority = line.split(":")

      # Append the guild ID and priority to the guilds list
      guilds.append((guild_id.strip(), int(priority.strip())))

  with tqdm.tqdm(guilds, desc="Guilds", unit="guild", position=0) as guild_progress:
    # Create a list of operations for bulk writing to MongoDB
    operations = []

    # Loop through the guild IDs
    for guild_id, priority in guild_progress:
      # Fetch the members for the guild using the Discord API
      members = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}/members?limit=1000", headers={ "Authorization": f"Bot {tokens[current_token]}" })
      members.raise_for_status()

      # Iterate through the members
      for member in members.json():
        # Convert the user ID to an int and store it
        member["user"]["_id"] = int(member["user"]["id"])

        # Add a ReplaceOne operation to the list of operations
        operations.append(pymongo.ReplaceOne({"_id": member["user"]["_id"]}, member["user"], upsert=True))

      # Sleep for a short time after processing
      time.sleep(1.5)

    # If there are any operations to perform
    if len(operations) > 0:
      # Perform the bulk write operation to MongoDB
      client["discorddump"]["users"].bulk_write(operations, ordered=False)

  # Use tqdm to show progress while iterating through the guilds
  with tqdm.tqdm(guilds, desc="Guilds", unit="guild", position=0) as guild_progress:
    # Loop through the guild IDs
    for guild_id, priority in guild_progress:
      # If the priority is less than or equal to 2
      if priority <= 2:
        # Reset the current token index to 0 to start with the first token
        current_token = 0

      # Fetch the channels for the guild using the Discord API
      channels = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers={ "Authorization": f"Bot {tokens[current_token]}" })
      channels.raise_for_status()

      # Use tqdm to show progress while iterating through the channels
      with tqdm.tqdm(channels.json(), desc=f"Guild {guild_id}", unit="channel", position=1, leave=False) as channel_progress:
        # Iterate through the channels
        for channel in channel_progress:
          # If the channel is not a text channel, skip it
          if channel["type"] not in (0, 1, 3, 5, 10, 11, 12):
            continue

          # Use tqdm to show progress while fetching messages for the channel
          with tqdm.tqdm(desc=f"Channel {channel['id']}", unit="message", position=2, leave=False) as message_progress:
            # Initialize the last message ID for pagination
            last_message_id = None

            # Fetch messages for the channel
            while True:
              # Build the query parameters for fetching messages
              params = { "limit": 100 }

              # If there is a last message ID
              if last_message_id:
                # Add it to the parameters for pagination
                params.update({ "before": last_message_id })

              # Fetch the messages for the channel
              messages = requests.get(f"https://discord.com/api/v10/channels/{channel['id']}/messages?{urllib.parse.urlencode(params)}", headers={ "Authorization": f"Bot {tokens[current_token]}" })
              messages.raise_for_status()

              # If the priority is greater than 2
              if priority > 2:
                # Rotate to the next token for the next request
                current_token = (current_token + 1) % len(tokens)

              # Check the rate limit headers
              ratelimit_remaining = messages.headers.get("x-ratelimit-remaining")
              ratelimit_reset_after = messages.headers.get("x-ratelimit-reset-after")

              # If the rate limit headers are present
              if ratelimit_remaining is not None and ratelimit_reset_after is not None:
                # If the remaining rate limit is less than or equal to 1
                if int(ratelimit_remaining) <= 1:
                  # Calculate the sleep time until the rate limit resets
                  sleep_time = (float(ratelimit_reset_after) - time.time()) + 5

                  # Ensure the sleep time is at least 1 second to avoid negative sleep time
                  if sleep_time < 0:
                    # Set a default sleep time if the calculated sleep time is negative
                    sleep_time = 5

                  # Log the rate limit hit and the sleep time
                  tqdm.tqdm.write(f"Rate limit hit for channel {channel['id']}. Sleeping for {sleep_time} seconds.")

                  # Sleep until the rate limit resets
                  time.sleep(sleep_time)

              # Get the messages data
              messages_data = messages.json()

              # Create a list of operations for bulk writing to MongoDB
              operations = []

              # Initialize a dict to store the unique attachment URLs
              attachment_urls = {}

              # Iterate through the messages
              for message in messages_data:
                # Convert the message ID to an int and store it
                message["_id"] = int(message["id"])

                # Add a ReplaceOne operation to the list of operations
                operations.append(pymongo.ReplaceOne({"_id": message["_id"]}, message, upsert=True))

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
                  attachment_url = url._replace(netloc="cdn.discordapp.com").geturl()

                  # Check if the URL path matches the pattern for attachments
                  if (match := re.match(r"^/attachments/(\d+)/(\d+)/([^/]+)$", url.path)):
                    # Add the attachment to the attachments dict
                    attachment_urls[f"{match.group(1)}_{match.group(2)}_{match.group(3)}"] = attachment_url

              # Download the attachments concurrently using the thread pool executor
              for key, url in attachment_urls.items():
                # Parse the URL of the request
                parsed_url = urllib.parse.urlparse(url)

                # Check if the URL path matches the pattern for attachments
                if (match := re.match(r"^/attachments/(\d+)/(\d+)/([^/]+)$", parsed_url.path)):
                  # If the file for the attachment already exists
                  if os.path.exists(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3))):
                    # Continue to avoid writing the same attachment again
                    continue

                  # Create the directory for the attachment
                  os.makedirs(os.path.join("data", "attachments", match.group(1), match.group(2)), exist_ok=True)

                  # Submit a task to the thread pool executor to download the attachment
                  executor.submit(download, url, os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3)))

              # If there are any operations to perform
              if len(operations) > 0:
                # Perform the bulk write operation to MongoDB
                client["discorddump"]["messages"].bulk_write(operations, ordered=False)

              # Get the number of messages fetched
              messages_num = len(messages_data)

              # Update the progress bar with the number of messages fetched
              message_progress.update(messages_num)

              # If there are no more messages, break the loop
              if messages_num == 0:
                break

              # Update the last message ID for pagination
              last_message_id = messages_data[-1]["id"]

              # If the priority is greater than 2
              if priority <= 2:
                # Sleep for a short time after processing a high priority guild to avoid hitting rate limits
                time.sleep(1.5)

if __name__ == "__main__":
  main()
