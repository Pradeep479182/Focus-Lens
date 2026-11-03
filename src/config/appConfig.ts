export const appConfig = {
  serviceProtocolVersion: 1,
  nativeCommands: {
    getCameraStatus: 'get_camera_status',
    startCvPipeline: 'start_cv_pipeline',
    stopCvPipeline: 'stop_cv_pipeline',
    processCameraFrame: 'process_camera_frame',
  },
  nativeEvents: {
    activitySignal: 'activity-signal',
    sessionEvent: 'session-event',
    cvResponse: 'cv-response',
  },
} as const;