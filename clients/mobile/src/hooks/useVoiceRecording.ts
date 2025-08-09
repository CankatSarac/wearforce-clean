import { useState, useCallback, useRef, useEffect } from 'react';
import { Platform, PermissionsAndroid, Alert } from 'react-native';
import Voice, { 
  SpeechRecognizedEvent, 
  SpeechResultsEvent, 
  SpeechErrorEvent,
  SpeechStartEvent,
  SpeechEndEvent,
} from '@react-native-voice/voice';
import AudioRecorderPlayer from 'react-native-audio-recorder-player';
import RNFS from 'react-native-fs';

interface UseVoiceRecordingReturn {
  isRecording: boolean;
  isListening: boolean;
  hasPermission: boolean;
  audioLevel: number;
  transcript: string;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<string | null>;
  startListening: () => Promise<void>;
  stopListening: () => Promise<void>;
  requestPermissions: () => Promise<boolean>;
}

const audioRecorderPlayer = new AudioRecorderPlayer();

export const useVoiceRecording = (): UseVoiceRecordingReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [transcript, setTranscript] = useState('');

  const recordingPath = useRef<string>('');
  const audioLevelTimer = useRef<NodeJS.Timeout>();

  // Check permissions on mount
  useEffect(() => {
    checkPermissions();
    setupVoiceRecognition();

    return () => {
      cleanup();
    };
  }, []);

  const checkPermissions = async () => {
    try {
      if (Platform.OS === 'android') {
        const grants = await PermissionsAndroid.requestMultiple([
          PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
          PermissionsAndroid.PERMISSIONS.WRITE_EXTERNAL_STORAGE,
          PermissionsAndroid.PERMISSIONS.READ_EXTERNAL_STORAGE,
        ]);

        const hasRecordPermission = grants['android.permission.RECORD_AUDIO'] === 'granted';
        const hasStoragePermission = grants['android.permission.WRITE_EXTERNAL_STORAGE'] === 'granted' ||
                                   grants['android.permission.READ_EXTERNAL_STORAGE'] === 'granted';

        setHasPermission(hasRecordPermission && hasStoragePermission);
      } else {
        // iOS permissions are handled by the system
        setHasPermission(true);
      }
    } catch (error) {
      console.error('Permission check failed:', error);
      setHasPermission(false);
    }
  };

  const requestPermissions = useCallback(async (): Promise<boolean> => {
    try {
      if (Platform.OS === 'android') {
        const grants = await PermissionsAndroid.requestMultiple([
          PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
          PermissionsAndroid.PERMISSIONS.WRITE_EXTERNAL_STORAGE,
          PermissionsAndroid.PERMISSIONS.READ_EXTERNAL_STORAGE,
        ]);

        const hasRecordPermission = grants['android.permission.RECORD_AUDIO'] === 'granted';
        const hasStoragePermission = grants['android.permission.WRITE_EXTERNAL_STORAGE'] === 'granted' ||
                                   grants['android.permission.READ_EXTERNAL_STORAGE'] === 'granted';

        const permissionGranted = hasRecordPermission && hasStoragePermission;
        setHasPermission(permissionGranted);
        return permissionGranted;
      } else {
        setHasPermission(true);
        return true;
      }
    } catch (error) {
      console.error('Permission request failed:', error);
      setHasPermission(false);
      return false;
    }
  }, []);

  const setupVoiceRecognition = () => {
    Voice.onSpeechStart = onSpeechStart;
    Voice.onSpeechEnd = onSpeechEnd;
    Voice.onSpeechError = onSpeechError;
    Voice.onSpeechResults = onSpeechResults;
    Voice.onSpeechPartialResults = onSpeechPartialResults;
    Voice.onSpeechRecognized = onSpeechRecognized;
  };

  const onSpeechStart = (event: SpeechStartEvent) => {
    console.log('Speech recognition started');
    setIsListening(true);
  };

  const onSpeechEnd = (event: SpeechEndEvent) => {
    console.log('Speech recognition ended');
    setIsListening(false);
    setAudioLevel(0);
  };

  const onSpeechError = (event: SpeechErrorEvent) => {
    console.error('Speech recognition error:', event.error);
    setIsListening(false);
    setAudioLevel(0);
    
    if (event.error?.message) {
      Alert.alert('Speech Recognition Error', event.error.message);
    }
  };

  const onSpeechResults = (event: SpeechResultsEvent) => {
    if (event.value && event.value.length > 0) {
      setTranscript(event.value[0]);
      console.log('Final speech result:', event.value[0]);
    }
  };

  const onSpeechPartialResults = (event: SpeechResultsEvent) => {
    if (event.value && event.value.length > 0) {
      setTranscript(event.value[0]);
      console.log('Partial speech result:', event.value[0]);
    }
  };

  const onSpeechRecognized = (event: SpeechRecognizedEvent) => {
    console.log('Speech recognized:', event.isFinal);
  };

  const startRecording = useCallback(async () => {
    if (!hasPermission) {
      const granted = await requestPermissions();
      if (!granted) {
        Alert.alert('Permission Required', 'Microphone permission is required to record audio.');
        return;
      }
    }

    if (isRecording) {
      console.warn('Already recording');
      return;
    }

    try {
      const timestamp = new Date().getTime();
      const fileName = `recording_${timestamp}.m4a`;
      const path = `${RNFS.DocumentDirectoryPath}/${fileName}`;
      recordingPath.current = path;

      const audioSet = {
        AudioEncoderAndroid: AudioRecorderPlayer.AudioEncoderAndroidType.AAC,
        AudioSourceAndroid: AudioRecorderPlayer.AudioSourceAndroidType.MIC,
        AVEncoderAudioQualityKeyIOS: AudioRecorderPlayer.AVEncoderAudioQualityIOSType.high,
        AVNumberOfChannelsKeyIOS: 1,
        AVFormatIDKeyIOS: AudioRecorderPlayer.AVFormatIDIOSType.mp4,
      };

      console.log('Starting audio recording at:', path);
      
      await audioRecorderPlayer.startRecorder(path, audioSet);
      setIsRecording(true);

      // Start monitoring audio level
      audioLevelTimer.current = setInterval(async () => {
        const result = await audioRecorderPlayer.onStatusUpdate;
        if (result && result.currentMetering) {
          // Normalize audio level to 0-1 range
          const normalizedLevel = Math.max(0, (result.currentMetering + 60) / 60);
          setAudioLevel(normalizedLevel);
        }
      }, 100);

    } catch (error) {
      console.error('Failed to start recording:', error);
      Alert.alert('Recording Error', 'Failed to start audio recording.');
      setIsRecording(false);
    }
  }, [hasPermission, isRecording, requestPermissions]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (!isRecording) {
      console.warn('Not currently recording');
      return null;
    }

    try {
      const result = await audioRecorderPlayer.stopRecorder();
      setIsRecording(false);
      setAudioLevel(0);

      if (audioLevelTimer.current) {
        clearInterval(audioLevelTimer.current);
      }

      console.log('Recording stopped:', result);
      
      // Read the recorded file
      if (recordingPath.current && await RNFS.exists(recordingPath.current)) {
        const audioData = await RNFS.readFile(recordingPath.current, 'base64');
        console.log('Audio file read, size:', audioData.length);
        return audioData;
      } else {
        console.error('Recording file not found');
        return null;
      }
    } catch (error) {
      console.error('Failed to stop recording:', error);
      setIsRecording(false);
      setAudioLevel(0);
      return null;
    }
  }, [isRecording]);

  const startListening = useCallback(async () => {
    if (!hasPermission) {
      const granted = await requestPermissions();
      if (!granted) {
        Alert.alert('Permission Required', 'Microphone permission is required for speech recognition.');
        return;
      }
    }

    if (isListening) {
      console.warn('Already listening');
      return;
    }

    try {
      setTranscript('');
      
      const options = {
        locale: 'en-US',
        partialResults: true,
        onDevice: false, // Use cloud recognition for better accuracy
        showPopup: false,
      };

      await Voice.start('en-US', options);
      console.log('Speech recognition started');
    } catch (error) {
      console.error('Failed to start speech recognition:', error);
      Alert.alert('Recognition Error', 'Failed to start speech recognition.');
    }
  }, [hasPermission, isListening, requestPermissions]);

  const stopListening = useCallback(async () => {
    if (!isListening) {
      console.warn('Not currently listening');
      return;
    }

    try {
      await Voice.stop();
      console.log('Speech recognition stopped');
    } catch (error) {
      console.error('Failed to stop speech recognition:', error);
    }
  }, [isListening]);

  const cleanup = () => {
    if (audioLevelTimer.current) {
      clearInterval(audioLevelTimer.current);
    }

    if (isRecording) {
      audioRecorderPlayer.stopRecorder().catch(console.error);
    }

    if (isListening) {
      Voice.stop().catch(console.error);
    }

    Voice.destroy().catch(console.error);
  };

  return {
    isRecording,
    isListening,
    hasPermission,
    audioLevel,
    transcript,
    startRecording,
    stopRecording,
    startListening,
    stopListening,
    requestPermissions,
  };
};