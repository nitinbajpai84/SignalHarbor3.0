import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DocumentLayout from "./DocumentLayout";
import type { LayoutDoc, LayoutSection } from "./api";

// ED1: a filled section stays editable (a list one line per item with add and remove; rows by cell).
const sec = (o: Partial<LayoutSection>): LayoutSection => ({ key: "k", heading: "H", instruction: "", example: "", required: false, type: "list", filled: true, value: [], edits: [], from: [], ...o });
const doc = (sections: LayoutSection[]): LayoutDoc => ({ kind: "intent_of_work", title: "Intent of work", template: { id: "t", name: "T", version: 1 }, choices: [], sections });

test("a filled list is edited line by line and saved through the section edit route", async () => {
  const save = vi.fn(async () => {});
  render(<DocumentLayout can save={save} doc={doc([sec({ key: "access", heading: "Who may see what", value: ["Only Nitin Guard", "Yakub"], edits: [{ label: "Who may see what", section: "template_fields", field: "access", value: "Only Nitin Guard\nYakub" }] })])} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Who may see what" }));
  const first = screen.getByLabelText("Item 1");
  await userEvent.clear(first); await userEvent.type(first, "Only Gerd");
  await userEvent.click(screen.getByRole("button", { name: "Remove item 2" }));
  await userEvent.click(screen.getByRole("button", { name: "Add item" }));
  await userEvent.type(screen.getByLabelText("Item 2"), "Yakub");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(save).toHaveBeenCalledWith({ section: "template_fields", field: "access", value: "Only Gerd\nYakub" });
});

test("a filled section made of rows edits only the cells that changed, and a signed document has no Edit", async () => {
  const save = vi.fn(async () => {});
  const s = sec({ key: "rules", heading: "Rules", type: "long_text", value: "Access: Only the CEO", edits: [{ label: "Access", section: "governance", field: "rule", index: 0, value: "Only the CEO" }] });
  const { rerender } = render(<DocumentLayout can save={save} doc={doc([s])} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit Rules" }));
  const box = screen.getByLabelText("Access");
  await userEvent.clear(box); await userEvent.type(box, "Only Gerd");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(save).toHaveBeenCalledWith({ section: "governance", field: "rule", index: 0, value: "Only Gerd" });
  rerender(<DocumentLayout can={false} save={save} doc={doc([s])} />);
  expect(screen.queryByRole("button", { name: "Edit Rules" })).toBeNull();
});
