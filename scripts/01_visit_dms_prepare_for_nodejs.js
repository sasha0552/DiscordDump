const fs = require("fs");
const path = require("path");

function traverse(dir, callback) {
  fs.readdirSync(dir).forEach((f) => {
    const dirPath = path.join(dir, f);
    const isDirectory = fs.statSync(dirPath).isDirectory();
    isDirectory ? traverse(dirPath, callback) : callback(path.join(dir, f));
  });
};

const allRecepients = new Set();

traverse("./data/package", (filePath) => {
  if (path.basename(filePath) === "channel.json") {
    const content = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    if (typeof content === "object" && content !== null && "type" in content && content.type === "DM") {
      if (Array.isArray(content.recipients)) {
        content.recipients.filter(x => /^\d+$/.test(x)).forEach((r) => allRecepients.add(r));
      }
    }
  }
});

fs.writeFileSync("./data/all_recipients.json", JSON.stringify(Array.from(allRecepients)));
