import { act, renderHook, waitFor } from "@testing-library/react";

import { usePolled } from "./usePolled";

// The board and the room refresh every few seconds; an answer to the person's own action must not be undone by an older refresh.

test("a refresh that started before the person's own action does not replace the newer answer", async () => {
  let release: (v: string) => void = () => undefined;
  const slow = new Promise<string>((r) => (release = r));
  const { result } = renderHook(() => usePolled<string>(() => slow, "k", 60_000));
  act(() => result.current.put("my answer"));
  await act(async () => {
    release("older view");
    await slow;
  });
  expect(result.current.data).toBe("my answer");
});

test("a later refresh does replace it, and a dropout keeps the view that is on screen", async () => {
  let n = 0;
  const { result } = renderHook(() => usePolled<string>(() => (++n === 2 ? Promise.reject(new Error("down")) : Promise.resolve(`view ${n}`)), "k2", 60_000));
  await waitFor(() => expect(result.current.data).toBe("view 1"));
  act(() => result.current.reload());
  await waitFor(() => expect(result.current.failure).not.toBeNull());
  expect(result.current.state).toBe("populated");
  expect(result.current.data).toBe("view 1");
  act(() => result.current.reload());
  await waitFor(() => expect(result.current.data).toBe("view 3"));
});
