/** Reads server-sent events from pieces of text as they arrive: an event is "data: ..." lines ended by a blank line. */
export function createEventReader(onData: (data: string) => void): (text: string) => void {
  let pending = "";
  return (text: string) => {
    pending += text.replace(/\r\n?/g, "\n");
    let end = pending.indexOf("\n\n");
    while (end !== -1) {
      const block = pending.slice(0, end);
      pending = pending.slice(end + 2);
      const lines = block.split("\n").filter((l) => l.startsWith("data:"));
      if (lines.length > 0) {
        onData(lines.map((l) => l.slice(5).replace(/^ /, "")).join("\n"));
      }
      end = pending.indexOf("\n\n");
    }
  };
}
