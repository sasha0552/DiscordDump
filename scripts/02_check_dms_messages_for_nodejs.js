const fs = require("fs");
const path = require("path");

function traverse(dir, callback) {
  fs.readdirSync(dir).forEach((f) => {
    const dirPath = path.join(dir, f);
    const isDirectory = fs.statSync(dirPath).isDirectory();
    isDirectory ? traverse(dirPath, callback) : callback(path.join(dir, f));
  });
};

const allMessages = new Set();

traverse("./data/package", (filePath) => {
  if (path.basename(filePath) === "channel.json") {
    const content = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    if (typeof content === "object" && content !== null && "type" in content && content.type === "DM") {
      const messages = JSON.parse(fs.readFileSync(path.join(path.dirname(filePath), "messages.json"), "utf-8"));
      messages.forEach((message) => allMessages.add(message.ID));
    }
  }
});

fs.writeFileSync("./data/all_messageids.json", JSON.stringify(Array.from(allMessages)));
