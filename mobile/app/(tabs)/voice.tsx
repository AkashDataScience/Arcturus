import React, { useState, useEffect } from 'react';
import { StyleSheet, TouchableOpacity, Animated, Platform } from 'react-native';
import { Audio } from 'expo-av';
import * as Haptics from 'expo-haptics';
import { Ionicons } from '@expo/vector-icons';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useDiscovery } from '@/context/DiscoveryContext';

export default function VoiceScreen() {
  const colorScheme = useColorScheme();
  const { gatewayUrl } = useDiscovery();
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [lastReply, setLastReply] = useState('');
  const [recognition, setRecognition] = useState<any>(null);
  const [pulseAnim] = useState(new Animated.Value(1));

  useEffect(() => {
    if (Platform.OS === 'web' && 'webkitSpeechRecognition' in window) {
      const SpeechRecognition = (window as any).webkitSpeechRecognition;
      const recog = new SpeechRecognition();
      recog.continuous = false;
      recog.interimResults = true;
      recog.onresult = (event: any) => {
        const text = event.results[0][0].transcript;
        setTranscript(text);
      };
      recog.onend = () => {
        setIsListening(false);
      };
      setRecognition(recog);
    }
  }, []);

  useEffect(() => {
    if (isListening) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.2,
            duration: 1000,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1000,
            useNativeDriver: true,
          }),
        ])
      ).start();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isListening]);

  async function startRecording() {
    try {
      // 1. Reset states
      setTranscript('');
      setLastReply('');

      // 2. Browser STT start
      if (recognition) {
        try { recognition.start(); } catch (e) { console.warn('Recognition start failed:', e); }
      }

      // 3. Audio Recording cleanup & start
      if (recording) {
        try { await recording.stopAndUnloadAsync(); } catch (e) { }
        setRecording(null);
      }

      const permission = await Audio.requestPermissionsAsync();
      if (permission.status === 'granted') {
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
        });

        // Add a small delay to ensure cleanup finished
        const { recording: newRecording } = await Audio.Recording.createAsync(
          Audio.RecordingOptionsPresets.HIGH_QUALITY
        );
        setRecording(newRecording);
        setIsListening(true);
        playLocalSound('https://www.soundjay.com/buttons/button-3.mp3');

        if (Platform.OS !== 'web') {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        }
      }
    } catch (err) {
      console.error('Failed to start recording', err);
      setIsListening(false);
      setRecording(null);
    }
  }

  async function stopRecording() {
    // If not listening or recording, just bail
    if (!isListening) return;

    setIsListening(false);
    setIsThinking(true);

    let uri = null;
    try {
      // 1. Stop Browser STT
      if (recognition) {
        try { recognition.stop(); } catch (e) { }
      }

      // 2. Stop Expo Audio
      if (recording) {
        try {
          await recording.stopAndUnloadAsync();
          uri = recording.getURI();
        } catch (e) {
          console.error('Recording stop failed:', e);
        } finally {
          setRecording(null);
        }
      }

      // 3. Upload & Process
      if (gatewayUrl) {
        const formData = new FormData();
        formData.append('session_id', 'mobile-session-1');

        // Use a timeout for the fetch to prevent hanging yellow state
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

        if (transcript) formData.append('text', transcript);

        if (uri && Platform.OS === 'web') {
          const blobResponse = await fetch(uri);
          const blob = await blobResponse.blob();
          formData.append('file', blob, 'mobile_voice.wav');
        } else if (uri) {
          // @ts-ignore
          formData.append('file', {
            uri: uri.replace('file://', ''),
            type: 'audio/wav',
            name: 'mobile_voice.wav',
          });
        }

        const response = await fetch(`${gatewayUrl}/api/nexus/mobile/voice/inbound`, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.ok) {
          const data = await response.json();
          console.log('Voice Response:', data);
          setLastReply(data.reply);

          if (Platform.OS !== 'web') {
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          }

          // Speak the reply using Browser TTS
          speakText(data.reply);
        }
      }
    } catch (err) {
      console.error('Failed to process voice:', err);
      // If we timed out or failed, let the user know
      setLastReply("Sorry, I had trouble processing that. Please try again.");
    } finally {
      setIsThinking(false);
    }
  }

  function speakText(text: string) {
    if (Platform.OS === 'web' && 'speechSynthesis' in window) {
      // Cancel any ongoing speech
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    } else {
      // TODO: Implement native TTS if needed
      console.log('Native TTS not implemented, playing success chirp instead');
      playLocalSound('https://www.soundjay.com/buttons/button-20.mp3');
    }
  }

  async function playLocalSound(url: string) {
    try {
      if (Platform.OS === 'web') {
        const audio = new (window as any).Audio(url);
        audio.volume = 0.5;
        await audio.play();
      } else {
        const { sound } = await Audio.Sound.createAsync({ uri: url });
        await sound.playAsync();
      }
    } catch (e) {
      console.warn('Playback failed:', e);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Voice Mode</Text>
        <Text style={styles.subtitle}>
          {isListening ? 'Listening to you...' : isThinking ? 'Arcturus is thinking...' : 'Tap and hold to talk'}
        </Text>
      </View>

      <View style={styles.content}>
        {transcript ? (
          <View style={styles.transcriptContainer}>
            <Ionicons name="chatbubble-ellipses-outline" size={20} color={Colors[colorScheme ?? 'light'].tint} style={{ marginBottom: 5 }} />
            <Text style={styles.transcriptText}>{transcript}</Text>
          </View>
        ) : null}

        <View style={styles.visualizerContainer}>
          <Animated.View
            style={[
              styles.pulseCircle,
              {
                transform: [{ scale: pulseAnim }],
                backgroundColor: isListening ? Colors[colorScheme ?? 'light'].tint : '#ccc'
              }
            ]}
          />
          <TouchableOpacity
            onPressIn={startRecording}
            onPressOut={stopRecording}
            activeOpacity={0.7}
            style={[
              styles.micButton,
              { backgroundColor: isListening ? Colors[colorScheme ?? 'light'].tint : isThinking ? '#ffa500' : '#888' }
            ]}
          >
            <Ionicons name={isListening ? "mic" : isThinking ? "hourglass-outline" : "mic-outline"} size={40} color="#fff" />
          </TouchableOpacity>
        </View>

        {lastReply ? (
          <View style={styles.replyContainer}>
            <Text style={styles.replyLabel}>ARCTURUS</Text>
            <Text style={styles.replyText}>{lastReply}</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.footer}>
        <Text style={styles.hint}>
          {isListening ? 'Release to send' : isThinking ? 'Processing audio...' : 'Arcturus is ready'}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 60,
  },
  header: {
    alignItems: 'center',
  },
  content: {
    flex: 1,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    opacity: 0.6,
  },
  transcriptContainer: {
    paddingHorizontal: 40,
    marginBottom: 40,
    alignItems: 'center',
  },
  transcriptText: {
    fontSize: 18,
    textAlign: 'center',
    fontStyle: 'italic',
    opacity: 0.8,
  },
  replyContainer: {
    marginTop: 40,
    paddingHorizontal: 30,
    alignItems: 'center',
  },
  replyLabel: {
    fontSize: 12,
    fontWeight: 'bold',
    opacity: 0.4,
    letterSpacing: 2,
    marginBottom: 5,
  },
  replyText: {
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
  },
  visualizerContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseCircle: {
    position: 'absolute',
    width: 140,
    height: 140,
    borderRadius: 70,
    opacity: 0.3,
  },
  micButton: {
    width: 100,
    height: 100,
    borderRadius: 50,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 5,
  },
  footer: {
    alignItems: 'center',
  },
  hint: {
    fontSize: 14,
    opacity: 0.5,
    fontStyle: 'italic',
  },
});
