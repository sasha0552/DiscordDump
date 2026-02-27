import json
import os
import re
import sys
import urllib.parse

import pymongo
import requests
import tqdm

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

  # Initialize a set to store the attachment URLs that have been checked
  checked = set()
  valid = set()

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
        # Check if the URL path matches the pattern for attachments                      
        if (match := re.match(r"^/attachments/(\d+)/(\d+)/([^/]+)$", url.path)):
          # If the file for the attachment exists
          if os.path.exists(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3))):
            # If the file for the attachment is not empty
            if not os.path.getsize(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3))) == 0:
              # Add the attachment URL to the set of valid URLs
              valid.add(attachment_url)

      # Add the attachment URL to the set of checked URLs
      checked.add(attachment_url)

  # Iterate through the valid URLs
  for url in valid:
    # Remove the valid URL from the set of checked URLs to avoid downloading it again
    checked.remove(url)

  # Print the number of attachments found
  print(f"Found {len(checked)} attachments to download")

  if True:
    # Convert the set of checked URLs to a list to allow indexing
    checked = list(checked)

    # Initialize a set to store the new URLs that will be returned by the API
    new_urls = set()

    # Initialize a variable to keep track of the current token index
    current_token = 0

    # Read the token from the .env file
    with open(".env", "r") as file:
      tokens = [line.split("=")[1].strip() for line in file if line.startswith("DISCORD_TOKEN")]

    # Iterate through the checked URLs in batches of 20
    for urls in [checked[i:i + 20] for i in range(0, len(checked), 20)]:
      # Post a message to the Discord API to check the attachments
      new_urls_resp = requests.post("https://discord.com/api/v9/attachments/refresh-urls", headers={ "Authorization": f"Bot {tokens[current_token]}" }, json={ "attachment_urls": urls })
      new_urls_resp.raise_for_status()

      # Get the refreshed URLs from the API response
      refreshed_urls = new_urls_resp.json().get("refreshed_urls", [])

      # Print a message indicating that the URLs have been refreshed
      print(f"Refreshed {len(refreshed_urls)}/{len(urls)} URLs")

      # Add the refreshed URLs to the set of new URLs
      for refreshed in refreshed_urls:
        # Add the refreshed URL to the set of new URLs
        new_urls.add(refreshed["refreshed"])

      # Rotate to the next token for the next request
      current_token = (current_token + 1) % len(tokens)

    # Update the set of checked URLs to only include the new URLs that will be downloaded
    checked = new_urls

  # Iterate through the attachments
  for attachment in tqdm.tqdm(checked, desc="Downloading attachments"):
    # Parse the URL of the request
    url = urllib.parse.urlparse(attachment)

    # If the URL path is not a string
    if type(url.path) is not str:
      # Skip it
      continue

    # Check if the URL path matches the pattern for attachments                      
    if (match := re.match(r"^/attachments/(\d+)/(\d+)/([^/]+)$", url.path)):
      # If the file for the attachment does not exist
      if not os.path.exists(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3))):
        # Check for path traversal in the attachment URL
        if ".." in match.group(1) or ".." in match.group(2) or ".." in match.group(3):
          # Continue to avoid writing the attachment with a path traversal in the filename
          continue

        # Create the directory for the attachment
        os.makedirs(os.path.join("data", "attachments", match.group(1), match.group(2)), exist_ok=True)

        # Download the file using the URL
        with requests.get(attachment, stream=True) as response:
          # If the response status code is not 200
          if response.status_code != 200:
            if response.text.strip() == "This content is no longer available.":
              # Print the error message
              tqdm.tqdm.write(f"Failed to download attachment {attachment.split('?')[0]}: Invalid parameters")
            else:
              # Print the error message
              tqdm.tqdm.write(f"Failed to download attachment {attachment.split('?')[0]}: HTTP {response.status_code}")

            # Skip the attachment
            continue

          # Size in bytes
          total_size = int(response.headers.get("content-length", 0))

          # Use tqdm to show progress while downloading the file
          with tqdm.tqdm(total=total_size, unit="B", unit_scale=True, position=1, leave=False) as progress_bar:
            # Open a file to write the content
            with open(os.path.join("data", "attachments", match.group(1), match.group(2), match.group(3)), "wb") as file:
              # Write the content to the file in chunks
              for chunk in response.iter_content(chunk_size=8192):
                # Update the progress bar with the size of the chunk
                progress_bar.update(len(chunk))

                # Write the chunk to the file
                file.write(chunk)

if __name__ == "__main__":
  main()
