import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, TouchableOpacity, Image, Platform } from 'react-native';
import { CameraView, useCameraPermissions, FlashMode } from 'expo-camera';
import * as MediaLibrary from 'expo-media-library';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';

export default function CameraScreen() {
    const colorScheme = useColorScheme();
    const [permission, requestPermission] = useCameraPermissions();
    const [facing, setFacing] = useState<'back' | 'front'>('front');
    const [flash, setFlash] = useState<FlashMode>('off');
    const [previewVisible, setPreviewVisible] = useState(false);
    const [capturedImage, setCapturedImage] = useState<any>(null);
    const cameraRef = useRef<any>(null);

    useEffect(() => {
        console.log('CameraScreen: Initialized. Permissions:', permission?.status);
        console.log('CameraScreen: Facing:', facing, 'Flash:', flash);
    }, [permission, facing, flash]);

    if (!permission) {
        // Camera permissions are still loading.
        return (
            <View style={styles.container}>
                <Text style={styles.errorText}>Initialising Camera...</Text>
            </View>
        );
    }

    if (!permission.granted) {
        // Camera permissions are not granted yet.
        return (
            <View style={styles.container}>
                <Text style={styles.errorText}>No access to camera</Text>
                <TouchableOpacity onPress={requestPermission} style={styles.grantButton}>
                    <Text style={styles.grantButtonText}>Grant Permission</Text>
                </TouchableOpacity>
                {Platform.OS === 'web' && (
                    <Text style={styles.subErrorText}>
                        Please ensure you are using HTTPS or localhost and have granted camera permissions in your browser.
                    </Text>
                )}
            </View>
        );
    }

    const takePicture = async () => {
        if (!cameraRef.current) return;
        try {
            console.log('📸 Shutter pressed...');
            const photo = await cameraRef.current.takePictureAsync();
            setCapturedImage(photo);
            setPreviewVisible(true);
        } catch (e) {
            console.error('Failed to take picture:', e);
        }
    };

    const saveAndSend = async () => {
        console.log('Sending photo to agent:', capturedImage.uri);
        setPreviewVisible(false);
        // TODO: Upload to gateway and send NodeInvocation
    };

    function toggleCameraFacing() {
        setFacing((current) => (current === 'back' ? 'front' : 'back'));
    }

    function toggleFlash() {
        setFlash((current) => {
            if (current === 'off') return 'on';
            if (current === 'on') return 'auto';
            return 'off';
        });
    }

    const flashIcon = flash === 'on' ? 'flash' : flash === 'auto' ? 'flash-auto' : 'flash-off';

    return (
        <View style={styles.container}>
            {previewVisible && capturedImage ? (
                <View style={styles.previewContainer}>
                    <Image source={{ uri: capturedImage.uri }} style={styles.preview} />

                    <TouchableOpacity
                        onPress={() => setPreviewVisible(false)}
                        style={[styles.previewButtonDiscard, styles.absLeft]}>
                        <MaterialCommunityIcons name="close" size={40} color="#fff" />
                    </TouchableOpacity>

                    <TouchableOpacity
                        onPress={saveAndSend}
                        style={[styles.previewButtonConfirm, styles.absRight]}>
                        <MaterialCommunityIcons name="check-bold" size={50} color="#fff" />
                    </TouchableOpacity>
                </View>
            ) : (
                <View style={styles.cameraContainer}>
                    <CameraView
                        style={styles.camera}
                        facing={facing}
                        flash={flash}
                        ref={cameraRef}
                    />

                    {/* Top Right: Flash Toggle */}
                    <TouchableOpacity style={[styles.sideButton, styles.absTopRight]} onPress={toggleFlash}>
                        <MaterialCommunityIcons name={flashIcon} size={28} color="white" />
                    </TouchableOpacity>

                    {/* Bottom Left: Flip Camera */}
                    <TouchableOpacity style={[styles.sideButton, styles.absBottomLeft]} onPress={toggleCameraFacing}>
                        <MaterialCommunityIcons name="camera-flip-outline" size={32} color="white" />
                    </TouchableOpacity>

                    {/* Bottom Center: Shutter Button */}
                    <TouchableOpacity style={[styles.captureButton, styles.absBottomCenter]} onPress={takePicture}>
                        <View style={styles.captureInner} />
                    </TouchableOpacity>
                </View>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#000',
    },
    cameraContainer: {
        flex: 1,
        width: '100%',
        backgroundColor: '#000',
    },
    camera: {
        flex: 1,
        width: '100%',
    },
    absTopRight: {
        position: 'absolute',
        top: 60,
        right: 30,
    },
    absBottomLeft: {
        position: 'absolute',
        bottom: 60,
        left: 30,
    },
    absBottomCenter: {
        position: 'absolute',
        bottom: 40,
        alignSelf: 'center',
        left: '50%',
        marginLeft: -40, // Half of width (80)
    },
    absLeft: {
        position: 'absolute',
        bottom: 60,
        left: 40,
    },
    absRight: {
        position: 'absolute',
        bottom: 50, // Higher than discard to center better with check icon
        right: 40,
    },
    sideButton: {
        width: 50,
        height: 50,
        borderRadius: 25,
        backgroundColor: 'rgba(0,0,0,0.5)',
        alignItems: 'center',
        justifyContent: 'center',
    },
    captureButton: {
        width: 80,
        height: 80,
        borderRadius: 40,
        borderWidth: 6,
        borderColor: 'white',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(255,255,255,0.2)',
    },
    captureInner: {
        width: 60,
        height: 60,
        borderRadius: 30,
        backgroundColor: 'white',
    },
    previewContainer: {
        flex: 1,
        width: '100%',
        backgroundColor: 'black',
        justifyContent: 'center',
    },
    preview: {
        width: '100%',
        height: '100%',
        resizeMode: 'contain',
    },
    previewButtonDiscard: {
        width: 70,
        height: 70,
        borderRadius: 35,
        backgroundColor: 'rgba(255, 59, 48, 0.9)',
        alignItems: 'center',
        justifyContent: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 4.65,
        elevation: 8,
    },
    previewButtonConfirm: {
        width: 90,
        height: 90,
        borderRadius: 45,
        backgroundColor: 'rgba(52, 199, 89, 1.0)',
        alignItems: 'center',
        justifyContent: 'center',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 4.65,
        elevation: 8,
    },
    errorText: {
        marginTop: 100,
        fontSize: 18,
        fontWeight: 'bold',
        textAlign: 'center',
        color: '#fff',
    },
    subErrorText: {
        fontSize: 14,
        textAlign: 'center',
        opacity: 0.6,
        paddingHorizontal: 40,
        color: '#fff',
        marginTop: 20,
    },
    grantButton: {
        alignSelf: 'center',
        backgroundColor: Colors.light.tint,
        padding: 15,
        borderRadius: 10,
        marginVertical: 20,
    },
    grantButtonText: {
        color: '#fff',
        fontWeight: 'bold',
    }
});
