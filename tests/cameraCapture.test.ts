import { afterEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';

import { CameraCaptureService } from '../src/services/cameraCapture.service.ts';

type MediaDevicesStub = { getUserMedia?: () => Promise<MediaStream> };

const originalNavigator = globalThis.navigator;
const originalWindow = globalThis.window;

function installBrowserStubs(mediaDevices: MediaDevicesStub): void {
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { mediaDevices },
  });
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
      setInterval: globalThis.setInterval,
      clearInterval: globalThis.clearInterval,
      requestAnimationFrame: () => 1,
      cancelAnimationFrame: () => undefined,
    },
  });
}

function restoreBrowserStubs(): void {
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: originalNavigator });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow });
}

const video = {
  muted: false,
  playsInline: false,
  srcObject: null,
  play: async () => undefined,
  pause: () => undefined,
} as unknown as HTMLVideoElement;

afterEach(restoreBrowserStubs);

describe('CameraCaptureService permission and device states', () => {
  it('reports a clear permission-denied state when browser access is rejected', async () => {
    installBrowserStubs({
      getUserMedia: async () => { throw new DOMException('Denied by user', 'NotAllowedError'); },
    });
    const service = new CameraCaptureService();

    await service.startCapture(video);

    assert.deepEqual(service.getStatus(), {
      state: 'permission_denied',
      reason: 'permission_denied',
      message: 'Camera access was denied. Allow camera access in system or app settings, then retry.',
    });
  });

  it('reports device-unavailable and device-in-use failures without throwing', async () => {
    installBrowserStubs({
      getUserMedia: async () => { throw new DOMException('No device', 'NotFoundError'); },
    });
    const missingDevice = new CameraCaptureService();
    await missingDevice.startCapture(video);
    assert.equal(missingDevice.getStatus().state, 'device_unavailable');

    installBrowserStubs({
      getUserMedia: async () => { throw new DOMException('Busy', 'NotReadableError'); },
    });
    const busyDevice = new CameraCaptureService();
    await busyDevice.startCapture(video);
    assert.equal(busyDevice.getStatus().state, 'device_in_use');
  });

  it('reports unsupported browser camera APIs as initialization failures', async () => {
    installBrowserStubs({});
    const service = new CameraCaptureService();

    await service.startCapture(video);

    assert.equal(service.getStatus().state, 'initialization_failed');
    assert.match(service.getStatus().message ?? '', /not supported/i);
  });

  it('reports a frame error when an active camera track is revoked or disconnected', async () => {
    let endedHandler: (() => void) | undefined;
    const track = {
      addEventListener: (_event: string, handler: () => void) => { endedHandler = handler; },
      removeEventListener: () => undefined,
      stop: () => undefined,
    };
    const stream = { getVideoTracks: () => [track] } as unknown as MediaStream;
    const frameVideo = {
      ...video,
      requestVideoFrameCallback: (callback: (now: number, metadata: { width: number; height: number }) => void) => {
        queueMicrotask(() => callback(0, { width: 640, height: 480 }));
        return 1;
      },
      cancelVideoFrameCallback: () => undefined,
    } as unknown as HTMLVideoElement;
    installBrowserStubs({ getUserMedia: async () => stream });
    const service = new CameraCaptureService();

    await service.startCapture(frameVideo);
    assert.equal(service.getStatus().state, 'active');

    endedHandler?.();
    assert.equal(service.getStatus().state, 'frame_error');
    assert.equal(service.getStatus().reason, 'frame_stopped');
  });
});
