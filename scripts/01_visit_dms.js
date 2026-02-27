const allRecipients = [/*INSERT HERE*/];

const iframe = document.createElement("iframe");
iframe.style.display = "none";
document.body.appendChild(iframe);
const cleanLocalStorage = iframe.contentWindow.localStorage;
const userId = JSON.parse(cleanLocalStorage.getItem("user_id_cache"));

(async () => {
  for (const recipient of allRecipients) {
    if (recipient === userId) continue;
    await Vencord.Util.openPrivateChannel({ recipientIds: [recipient] });
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
})();