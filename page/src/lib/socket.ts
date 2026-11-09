import { io, type Socket } from "socket.io-client";
import Constants from "expo-constants";

const SOCKET_URL =
  Constants.expoConfig?.extra?.apiUrl || process.env.EXPO_PUBLIC_API_URL;

if (!SOCKET_URL) {
  throw new Error("EXPO_PUBLIC_API_URL is not set");
}

let socket: Socket | null = null;

export function getSocket(): Socket | null {
  return socket;
}

export function connectSocket(userId?: number): Socket {
  if (socket?.connected) return socket;

  socket = io(SOCKET_URL, {
    transports: ["websocket"],
    autoConnect: true,
  });

  socket.on("connect", () => {
    if (userId != null) socket?.emit("authenticate", { user_id: userId });
  });

  return socket;
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}

export function onSocketEvent<T = unknown>(
  event: string,
  callback: (data: T) => void,
): void {
  socket?.on(event, callback);
}

export function offSocketEvent<T = unknown>(
  event: string,
  callback: (data: T) => void,
): void {
  socket?.off(event, callback);
}
