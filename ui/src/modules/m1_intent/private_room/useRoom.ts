import { useLoad } from "../useLoad";
import { getLibrary, getRoom, type Library, type Room } from "./roomApi";

export interface Loaded {
  room: Room;
  library: Library;
}

/** The private room and its library as one load: shared by the legacy room screen and the wall's North panel. */
export const useRoom = (sessionId: string) =>
  useLoad<Loaded>(async () => {
    const [room, library] = await Promise.all([getRoom(sessionId), getLibrary(sessionId)]);
    return { room, library };
  }, sessionId);
