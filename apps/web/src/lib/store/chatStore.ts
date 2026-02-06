/**
 * Chat Store
 * State management for the conversational agent system using Zustand
 */

import { create } from 'zustand';
import { ChatClient, createChatClient } from '../ws/chatClient';
import type {
  WsEvent,
  ChatMessage,
  ActionState,
  ConversationState,
} from '../schema/conversation';

interface ChatStore extends ConversationState {
  // WebSocket client
  client: ChatClient | null;

  // Actions
  connect: (conversationId: string, projectId: string, chapterId?: string) => void;
  disconnect: () => void;
  sendMessage: (content: string) => void;
  clearMessages: () => void;
  setError: (error: string | null) => void;

  // Internal handlers
  handleWsEvent: (event: WsEvent) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  // Initial state
  id: null,
  projectId: null,
  chapterId: null,
  messages: [],
  isConnected: false,
  isStreaming: false,
  pendingActions: [],
  error: null,
  client: null,

  // Connect to WebSocket
  connect: (conversationId: string, projectId: string, chapterId?: string) => {
    const { client, disconnect } = get();

    // Disconnect existing client
    if (client) {
      disconnect();
    }

    // Create new client
    const newClient = createChatClient({
      conversationId,
      onEvent: (event) => get().handleWsEvent(event),
      onConnect: () => {
        console.log('Chat connected');
        set({ isConnected: true, error: null });
      },
      onDisconnect: () => {
        console.log('Chat disconnected');
        set({ isConnected: false });
      },
      onError: (error) => {
        console.error('Chat error:', error);
        set({ error: error.message, isConnected: false });
      },
      autoReconnect: true,
    });

    newClient.connect();

    set({
      id: conversationId,
      projectId,
      chapterId: chapterId ?? null,
      client: newClient,
      messages: [],
      pendingActions: [],
      error: null,
    });
  },

  // Disconnect from WebSocket
  disconnect: () => {
    const { client } = get();
    if (client) {
      client.disconnect();
    }
    set({
      client: null,
      isConnected: false,
      isStreaming: false,
    });
  },

  // Send a message
  sendMessage: (content: string) => {
    const { client, isConnected, messages } = get();

    if (!client || !isConnected) {
      set({ error: 'Not connected to chat server' });
      return;
    }

    try {
      // Add user message to UI immediately
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      };

      set({
        messages: [...messages, userMessage],
        error: null,
      });

      // Send to server
      client.sendMessage(content);
    } catch (error) {
      console.error('Failed to send message:', error);
      set({ error: (error as Error).message });
    }
  },

  // Clear all messages
  clearMessages: () => {
    set({ messages: [], pendingActions: [] });
  },

  // Set error
  setError: (error: string | null) => {
    set({ error });
  },

  // Handle WebSocket events
  handleWsEvent: (event: WsEvent) => {
    const { messages, pendingActions } = get();

    switch (event.type) {
      case 'connected':
        console.log('Connected to conversation:', event.conversation_id);
        break;

      case 'assistant_message':
        // Complete assistant message
        set({
          messages: [
            ...messages,
            {
              id: event.message_id || `assistant-${Date.now()}`,
              role: 'assistant',
              content: event.content,
              timestamp: new Date(),
              intent: event.intent,
            },
          ],
          isStreaming: false,
        });
        break;

      case 'assistant_message_chunk':
      case 'message_chunk':
        // Streaming chunk
        set({ isStreaming: true });

        const lastMessage = messages[messages.length - 1];
        if (lastMessage && lastMessage.role === 'assistant' && lastMessage.isStreaming) {
          // Append to existing streaming message
          const updatedMessages = [...messages];
          updatedMessages[updatedMessages.length - 1] = {
            ...lastMessage,
            content: lastMessage.content + event.chunk,
          };
          set({ messages: updatedMessages });
        } else {
          // Create new streaming message
          set({
            messages: [
              ...messages,
              {
                id: event.message_id || `assistant-${Date.now()}`,
                role: 'assistant',
                content: event.chunk,
                timestamp: new Date(),
                isStreaming: true,
              },
            ],
          });
        }

        if (event.is_final) {
          set({ isStreaming: false });
        }
        break;

      case 'message_complete':
        // Mark streaming as complete
        const completedMessages = messages.map((msg) =>
          msg.id === event.message_id ? { ...msg, isStreaming: false } : msg
        );
        set({ messages: completedMessages, isStreaming: false });
        break;

      case 'tool_call':
        // Add tool call to last assistant message
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          const updatedMsgs = [...messages];
          updatedMsgs[updatedMsgs.length - 1] = {
            ...lastMsg,
            toolCalls: [...(lastMsg.toolCalls || []), event.tool_call],
          };
          set({ messages: updatedMsgs });
        }
        break;

      case 'action_started':
        // Add new pending action
        set({
          pendingActions: [
            ...pendingActions,
            {
              id: event.action_id,
              type: event.action_type,
              description: event.description,
              status: 'running',
              progress: 0,
            },
          ],
        });
        break;

      case 'action_progress':
        // Update action progress
        const progressActions = pendingActions.map((action) =>
          action.id === event.action_id
            ? {
                ...action,
                progress: event.progress,
                description: event.description || action.description,
                previewUrl: event.preview_url || action.previewUrl,
              }
            : action
        );
        set({ pendingActions: progressActions });
        break;

      case 'action_completed':
        // Mark action as completed
        const completedActions = pendingActions.map((action) =>
          action.id === event.action_id
            ? {
                ...action,
                status: 'completed' as const,
                progress: 1,
                result: event.result,
              }
            : action
        );
        set({ pendingActions: completedActions });

        // Remove completed action after 3 seconds
        setTimeout(() => {
          const currentActions = get().pendingActions;
          set({
            pendingActions: currentActions.filter((a) => a.id !== event.action_id),
          });
        }, 3000);
        break;

      case 'error':
        console.error('Chat error:', event.error);
        set({ error: event.error, isStreaming: false });
        break;

      default:
        console.log('Unhandled event type:', event.type);
    }
  },
}));
