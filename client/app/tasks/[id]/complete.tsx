import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, Alert, ActivityIndicator } from 'react-native';
import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useMutation } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { submitTask } from '@/src/features/tasks/api';

export default function TaskCompleteScreen() {
  const { id, submission_id } = useLocalSearchParams<{ id: string; submission_id: string }>();
  
  const [proofImage, setProofImage] = useState<string | null>(null);
  const [proofUrl, setProofUrl] = useState('');
  const [proofText, setProofText] = useState('');

  const submitMutation = useMutation({
    mutationFn: () =>
      submitTask(Number(id), {
        proof_image_base64: proofImage,
        proof_url: proofUrl || null,
        proof_text: proofText || null,
      }),
    onSuccess: () => {
      Alert.alert(
        'Submitted!',
        'Your submission is being verified. You\'ll be notified once approved.',
        [
          {
            text: 'View My Submissions',
            onPress: () => router.push('/tasks/history'),
          },
        ]
      );
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to submit task');
    },
  });

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    
    if (status !== 'granted') {
      Alert.alert('Permission Required', 'Please grant camera roll permissions to upload proof.');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      quality: 0.8,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      // Add data URI prefix for Cloudinary
      const base64WithPrefix = `data:image/jpeg;base64,${result.assets[0].base64}`;
      setProofImage(base64WithPrefix);
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    
    if (status !== 'granted') {
      Alert.alert('Permission Required', 'Please grant camera permissions to take a photo.');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      quality: 0.8,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      const base64WithPrefix = `data:image/jpeg;base64,${result.assets[0].base64}`;
      setProofImage(base64WithPrefix);
    }
  };

  const handleSubmit = () => {
    if (!proofImage && !proofUrl && !proofText) {
      Alert.alert('Proof Required', 'Please provide proof of task completion.');
      return;
    }

    Alert.alert(
      'Submit Task',
      'Once submitted, your proof will be verified by AI. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Submit',
          onPress: () => submitMutation.mutate(),
        },
      ]
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#333" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Submit Proof</Text>
      </View>

      {/* Instructions */}
      <View style={styles.infoCard}>
        <Ionicons name="information-circle" size={24} color="#6C5CE7" />
        <Text style={styles.infoText}>
          Upload clear proof of task completion. AI will verify your submission automatically.
        </Text>
      </View>

      {/* Screenshot Upload */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          <Ionicons name="camera" size={18} color="#333" /> Screenshot Proof
        </Text>
        
        {proofImage ? (
          <View style={styles.imagePreview}>
            <View style={styles.imageUploadedBox}>
              <Ionicons name="checkmark-circle" size={48} color="#00B894" />
              <Text style={styles.imageUploadedText}>Screenshot Uploaded</Text>
            </View>
            <TouchableOpacity onPress={() => setProofImage(null)} style={styles.removeImageButton}>
              <Text style={styles.removeImageText}>Remove</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.uploadButtons}>
            <TouchableOpacity style={styles.uploadButton} onPress={pickImage}>
              <Ionicons name="images" size={24} color="#6C5CE7" />
              <Text style={styles.uploadButtonText}>Choose from Gallery</Text>
            </TouchableOpacity>
            
            <TouchableOpacity style={styles.uploadButton} onPress={takePhoto}>
              <Ionicons name="camera" size={24} color="#6C5CE7" />
              <Text style={styles.uploadButtonText}>Take Photo</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* URL Proof */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          <Ionicons name="link" size={18} color="#333" /> URL Proof (Optional)
        </Text>
        <TextInput
          style={styles.input}
          placeholder="https://twitter.com/yourhandle"
          value={proofUrl}
          onChangeText={setProofUrl}
          autoCapitalize="none"
          keyboardType="url"
        />
      </View>

      {/* Text Proof */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          <Ionicons name="document-text" size={18} color="#333" /> Text Proof (Optional)
        </Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Enter confirmation code, survey response, or review text..."
          value={proofText}
          onChangeText={setProofText}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
        />
      </View>

      {/* Submit Button */}
      <TouchableOpacity
        style={[styles.submitButton, submitMutation.isPending && styles.submitButtonDisabled]}
        onPress={handleSubmit}
        disabled={submitMutation.isPending}
      >
        {submitMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <>
            <Ionicons name="checkmark-circle" size={24} color="#fff" />
            <Text style={styles.submitButtonText}>Submit for Verification</Text>
          </>
        )}
      </TouchableOpacity>

      {/* Cancel Button */}
      <TouchableOpacity style={styles.cancelButton} onPress={() => router.back()}>
        <Text style={styles.cancelButtonText}>Cancel</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 32,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#fff',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  infoCard: {
    flexDirection: 'row',
    backgroundColor: '#E3F2FD',
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
    gap: 12,
  },
  infoText: {
    flex: 1,
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
  },
  section: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
  },
  uploadButtons: {
    gap: 12,
  },
  uploadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    backgroundColor: '#f5f5f5',
    borderRadius: 12,
    padding: 18,
    borderWidth: 2,
    borderColor: '#6C5CE7',
    borderStyle: 'dashed',
  },
  uploadButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6C5CE7',
  },
  imagePreview: {
    alignItems: 'center',
  },
  imageUploadedBox: {
    alignItems: 'center',
    padding: 24,
  },
  imageUploadedText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#00B894',
    marginTop: 12,
  },
  removeImageButton: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#ff6b6b',
    borderRadius: 8,
    marginTop: 12,
  },
  removeImageText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  input: {
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: '#333',
  },
  textArea: {
    minHeight: 100,
    paddingTop: 12,
  },
  submitButton: {
    backgroundColor: '#00B894',
    borderRadius: 12,
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    shadowColor: '#00B894',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
    marginBottom: 12,
  },
  submitButtonDisabled: {
    backgroundColor: '#ccc',
    shadowOpacity: 0,
    elevation: 0,
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  cancelButton: {
    padding: 18,
    alignItems: 'center',
  },
  cancelButtonText: {
    color: '#666',
    fontSize: 16,
    fontWeight: '600',
  },
});
