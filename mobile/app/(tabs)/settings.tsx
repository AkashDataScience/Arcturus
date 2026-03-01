import React, { useState } from 'react';
import { StyleSheet, Switch, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';

export default function SettingsScreen() {
    const colorScheme = useColorScheme();
    const [notifications, setNotifications] = useState(true);
    const [voiceWake, setVoiceWake] = useState(true);
    const [highQualityAudio, setHighQualityAudio] = useState(false);

    const SettingRow = ({ icon, label, value, onValueChange, isToggle = true }: any) => (
        <View style={styles.settingRow}>
            <View style={styles.settingLeft}>
                <Ionicons name={icon} size={24} color={Colors[colorScheme ?? 'light'].text} style={styles.icon} />
                <Text style={styles.settingLabel}>{label}</Text>
            </View>
            {isToggle ? (
                <Switch
                    value={value}
                    onValueChange={onValueChange}
                    trackColor={{ false: '#767577', true: Colors[colorScheme ?? 'light'].tint }}
                />
            ) : (
                <Ionicons name="chevron-forward" size={20} color="#888" />
            )}
        </View>
    );

    return (
        <ScrollView style={styles.container}>
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>Interaction</Text>
                <SettingRow
                    icon="notifications-outline"
                    label="Push Notifications"
                    value={notifications}
                    onValueChange={setNotifications}
                />
                <SettingRow
                    icon="mic-outline"
                    label="Voice Wake (Hey Arcturus)"
                    value={voiceWake}
                    onValueChange={setVoiceWake}
                />
                <SettingRow
                    icon="musical-notes-outline"
                    label="High Quality Audio"
                    value={highQualityAudio}
                    onValueChange={setHighQualityAudio}
                />
            </View>

            <View style={styles.section}>
                <Text style={styles.sectionTitle}>Account & Sync</Text>
                <SettingRow icon="person-outline" label="Profile Settings" isToggle={false} />
                <SettingRow icon="sync-outline" label="Device Pairing" isToggle={false} />
                <SettingRow icon="cloud-done-outline" label="Mnemo Memory Sync" value={true} isToggle={true} />
            </View>

            <View style={styles.footer}>
                <Text style={styles.version}>Arcturus v1.0.0 (Orbit)</Text>
            </View>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    section: {
        marginTop: 30,
        paddingHorizontal: 20,
    },
    sectionTitle: {
        fontSize: 14,
        fontWeight: 'bold',
        color: '#888',
        textTransform: 'uppercase',
        marginBottom: 10,
        marginLeft: 5,
    },
    settingRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingVertical: 15,
        borderBottomWidth: 1,
        borderBottomColor: '#222',
    },
    settingLeft: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    icon: {
        marginRight: 15,
    },
    settingLabel: {
        fontSize: 16,
    },
    footer: {
        marginTop: 50,
        paddingBottom: 40,
        alignItems: 'center',
    },
    version: {
        fontSize: 12,
        color: '#888',
    },
});
