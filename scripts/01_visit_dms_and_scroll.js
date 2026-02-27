// Utility function to generate random int between values
function randomBetween(a, b) {
  return Math.floor(Math.random() * (b - a + 1)) + a;
}

// Utility function to pause execution for a given number of milliseconds
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Utility function to check if element is in viewport
function isInViewport(element) {
  const rect = element.getBoundingClientRect();

  return (
    rect.bottom > 0 &&
    rect.right > 0 &&
    rect.top < window.innerHeight &&
    rect.left < window.innerWidth
  );
}

async function scrollMessages() {
  // Selector for the scrollable container
  const SELECTOR_SCROLLER = "div.messagesWrapper__36d07 > div.scroller__36d07"

  // Selector that indicates we've reached the beginning
  const SELECTOR_BEGINNING = SELECTOR_SCROLLER + " > div > ol > div.container__00de6";

  // Selector that selects dummy elements when messages is loading
  const SELECTOR_LOADING = SELECTOR_SCROLLER + " > div > ol > div.wrapper_d852db";

  // Cache the scroller element to avoid querying every iteration
  const scroller = document.querySelector(SELECTOR_SCROLLER);

  // If the scroller is not found
  if (!scroller) {
    // Exit early
    return false;
  }

  // Keep scrolling upward until the beginning element exists
  while (!document.querySelector(SELECTOR_BEGINNING)) {
    // If messages are loading
    while (isInViewport(document.querySelector(SELECTOR_LOADING))) {
      // Wait 100ms
      await sleep(100);
    }

    // Scroll up
    scroller.scrollBy({ top: -randomBetween(300, 600) });

    // Wait before the next scroll step
    await sleep(randomBetween(600, 1000));
  }

  // Return true when scrolling completes
  return true;
}

(async () => {
  // Iterate over all recipients
  for (recipient of all_recipients) {
    // Log the recipient being processed
    console.log("Processing recipient " + recipient);

    // Open DM with recipient
    await Vencord.Util.openPrivateChannel({ recipientIds: [recipient] });

    // Wait before trying to scroll messages to ensure the channel has loaded
    await sleep(5000);

    // Scroll messages
    await scrollMessages();

    // Wait before moving to the next DM
    await sleep(5000);
  }
})();
