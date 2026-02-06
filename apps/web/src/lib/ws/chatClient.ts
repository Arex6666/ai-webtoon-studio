/**
 * Chat WebSocket Client
 * Handles real-time communication with the conversational agent system
 */

import type { WsEvent, WsUserMessageEvent } from '../schema/conversation';

export type ChatEventHandler = (event: WsEvent) => void;

export interface ChatClientOptions {
  conversationId: string;
  onEvent: ChatEventHandler;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
  heartbeatInterval?: number;
}

export class ChatClient {
  private ws: WebSocket | null = null;
  private conversationId: string;
  private onEvent: ChatEventHandler;
  private onConnect?: () => void;
  private onDisconnect?: () => void;
  private onError?: (error: Error) => void;
  private autoReconnect: boolean;
  private reconnectInterval: number;
  private heartbeatInterval: number;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private isManualClose = false;

  constructor(options: ChatClientOptions) {
    this.conversationId = options.conversationId;
    this.onEvent = options.onEvent;
    this.onConnect = options.onConnect;
    this.onDisconnect = options.onDisconnect;
    this.onError = options.onError;
    this.autoReconnect = options.autoReconnect ?? true;
    this.reconnectInterval = options.reconnectInterval ?? 3000;
    this.heartbeatInterval = options.heartbeatInterval ?? 30000;
  }

  /**
   * Connect to the WebSocket server
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }

    this.isManualClose = false;

    // Determine WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/v1/ws/chat?conversation_id=${this.conversationId}`;

    console.log(`Connecting to chat WebSocket: ${wsUrl}`);

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('Chat WebSocket connected');
        this.onConnect?.();
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WsEvent;

          // Handle pong response
          if (data.type === 'pong') {
            return;
          }

          this.onEvent(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
          this.onError?.(error as Error);
        }
      };

      this.ws.onerror = (event) => {
        console.error('Chat WebSocket error:', event);
        this.onError?.(new Error('WebSocket connection error'));
      };

      this.ws.onclose = (event) => {
        console.log('Chat WebSocket closed:', event.code, event.reason);
        this.stopHeartbeat();
        this.onDisconnect?.();

        // Auto-reconnect if not manually closed
        if (!this.isManualClose && this.autoReconnect) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.onError?.(error as Error);
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    this.isManualClose = true;
    this.stopHeartbeat();
    this.clearReconnectTimer();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send a user message
   */
  sendMessage(content: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not connected');
    }

    const message: WsUserMessageEvent = {
      type: 'user_message',
      content,
    };

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Send a ping to keep the connection alive
   */
  private sendPing(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    this.ws.send(JSON.stringify({ type: 'ping' }));
  }

  /**
   * Start heartbeat timer
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.sendPing();
    }, this.heartbeatInterval);
  }

  /**
   * Stop heartbeat timer
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Schedule a reconnection attempt
   */
  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    console.log(`Scheduling reconnect in ${this.reconnectInterval}ms`);

    this.reconnectTimer = setTimeout(() => {
      console.log('Attempting to reconnect...');
      this.connect();
    }, this.reconnectInterval);
  }

  /**
   * Clear reconnection timer
   */
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get connection state
   */
  getReadyState(): number | null {
    return this.ws?.readyState ?? null;
  }
}

/**
 * Create a chat client instance
 */
export function createChatClient(options: ChatClientOptions): ChatClient {
  return new ChatClient(options);
}
