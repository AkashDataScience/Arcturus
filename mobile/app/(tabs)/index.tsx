import React, { useState, useRef, useEffect } from 'react';
import { StyleSheet, TextInput, KeyboardAvoidingView, Platform, FlatList, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useDiscovery } from '@/context/DiscoveryContext';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'agent';
  timestamp: Date;
}

export default function ChatScreen() {
  const colorScheme = useColorScheme();
  const { gatewayUrl } = useDiscovery();
  const [inputText, setInputText] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Hello! I am Arcturus. How can I help you today?',
      sender: 'agent',
      timestamp: new Date(),
    },
  ]);
  const flatListRef = useRef<FlatList>(null);

  const sendMessage = async () => {
    const text = inputText.trim();
    if (text === '' || isThinking) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: text,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText('');
    setIsThinking(true);

    // Logic to send to gateway
    if (gatewayUrl) {
      try {
        const response = await fetch(`${gatewayUrl}/api/nexus/mobile/inbound`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: 'mobile-session-1',
            text: userMessage.text,
            sender_id: 'mobile-user',
            sender_name: 'Mobile User',
            node_id: 'mobile-node-1',
          }),
        });

        if (response.ok) {
          const result = await response.json();
          const replyText = result.agent_response?.reply || result.formatted_text;

          if (replyText) {
            const agentMessage: Message = {
              id: Date.now().toString() + '-agent',
              text: replyText,
              sender: 'agent',
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, agentMessage]);
          }
        }
      } catch (err) {
        console.error('Failed to send message:', err);
      } finally {
        setIsThinking(false);
      }
    } else {
      setIsThinking(false);
    }
  };

  const handleKeyPress = (e: any) => {
    if (Platform.OS === 'web' && e.nativeEvent.key === 'Enter' && !e.nativeEvent.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const renderMessage = ({ item }: { item: Message }) => (
    <View style={[
      styles.messageBubble,
      item.sender === 'user' ? styles.userBubble : styles.agentBubble,
      { backgroundColor: item.sender === 'user' ? Colors[colorScheme ?? 'light'].tint : '#333' }
    ]}>
      <Text style={styles.messageText}>{item.text}</Text>
    </View>
  );

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
      keyboardVerticalOffset={90}
    >
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        ListFooterComponent={isThinking ? (
          <View style={[styles.messageBubble, styles.agentBubble, styles.thinkingBubble]}>
            <Text style={styles.thinkingText}>Arcturus is thinking...</Text>
          </View>
        ) : null}
      />

      <View style={styles.inputContainer}>
        <TextInput
          style={[styles.input, { color: Colors[colorScheme ?? 'light'].text }]}
          placeholder="Type a message..."
          placeholderTextColor="#888"
          value={inputText}
          onChangeText={setInputText}
          onKeyPress={handleKeyPress}
          multiline
          blurOnSubmit={false}
        />
        <TouchableOpacity
          style={[styles.sendButton, (isThinking || !inputText.trim()) && { opacity: 0.5 }]}
          onPress={sendMessage}
          disabled={isThinking || !inputText.trim()}
        >
          <Ionicons
            name={isThinking ? "hourglass-outline" : "send"}
            size={24}
            color={Colors[colorScheme ?? 'light'].tint}
          />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  messageList: {
    padding: 20,
    paddingBottom: 40,
  },
  messageBubble: {
    padding: 12,
    borderRadius: 20,
    marginBottom: 10,
    maxWidth: '80%',
  },
  userBubble: {
    alignSelf: 'flex-end',
    borderBottomRightRadius: 2,
  },
  agentBubble: {
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 2,
  },
  messageText: {
    color: '#fff',
    fontSize: 16,
  },
  thinkingBubble: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#444',
  },
  thinkingText: {
    color: '#aaa',
    fontSize: 14,
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: '#333',
    paddingBottom: Platform.OS === 'ios' ? 30 : 10,
  },
  input: {
    flex: 1,
    paddingHorizontal: 15,
    paddingVertical: 10,
    fontSize: 16,
    maxHeight: 100,
  },
  sendButton: {
    padding: 10,
  },
});
