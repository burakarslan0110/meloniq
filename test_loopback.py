"""Test script for loopback device detection."""
import pyaudiowpatch as pyaudio

p = pyaudio.PyAudio()

print('=== WASAPI Loopback Devices ===')
try:
    for dev in p.get_loopback_device_info_generator():
        print(f"  [{dev['index']}] {dev['name']}")
        print(f"      Channels: {dev['maxInputChannels']}, Rate: {dev['defaultSampleRate']}")
except Exception as e:
    print(f'Error: {e}')

print()
print('=== All WASAPI Devices ===')
for i in range(p.get_host_api_count()):
    api = p.get_host_api_info_by_index(i)
    if 'WASAPI' in api['name']:
        print(f"Host API: {api['name']}")
        for j in range(api['deviceCount']):
            dev = p.get_device_info_by_host_api_device_index(i, j)
            print(f"  [{dev['index']}] {dev['name']}")
            print(f"      In: {dev['maxInputChannels']}, Out: {dev['maxOutputChannels']}, Rate: {dev['defaultSampleRate']}")

p.terminate()
