import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import type { ActivityEvent, Session } from '../src/types/index.ts';
import {
  calculateDashboardMetrics,
  getDashboardAnalytics,
} from '../src/services/dashboardMetrics.service.ts';
import {
  activityEventRepository,
  sessionRepository,
} from '../src/services/db.service.ts';

const t0 = Date.parse('2026-10-27T08:00:00.000Z');

function session(id: string, elapsedSeconds: number, status: Session['status'] = 'completed'): Session {
  return {
    id,
    status,
    plannedDurationSeconds: 1_500,
    startedAt: new Date(t0).toISOString(),
    pausedAt: status === 'paused' ? new Date(t0 + 60_000).toISOString() : null,
    endedAt: ['completed', 'cancelled', 'interrupted'].includes(status)
      ? new Date(t0 + elapsedSeconds * 1_000).toISOString()
      : null,
    elapsedSeconds,
    pausedDurationSeconds: 0,
  };
}

function away(id: string, startedAt: number, duration: number, sessionId = 's1'): ActivityEvent {
  return {
    id,
    sessionId,
    type: 'away',
    timestamp: startedAt + 300_000,
    awayStartedAt: startedAt,
    thresholdReachedAt: startedAt + 300_000,
    endedAt: startedAt + duration * 1_000,
    duration,
  };
}

describe('dashboard metrics', () => {
  it('loads analytics events once and keeps session-specific away totals', async () => {
    const sessions = [session('s1', 1_000), session('s2', 500)];
    const events = [
      away('a1', t0, 60, 's1'),
      away('a2', t0 + 500_000, 30, 's2'),
    ];
    const originalGetAll = sessionRepository.getAll;
    const originalListAll = activityEventRepository.listAll;
    const originalListBySession = activityEventRepository.listBySession;
    let eventQueries = 0;
    let perSessionQueries = 0;

    sessionRepository.getAll = async () => sessions;
    activityEventRepository.listAll = async () => {
      eventQueries += 1;
      return events;
    };
    activityEventRepository.listBySession = async () => {
      perSessionQueries += 1;
      return [];
    };

    try {
      const analytics = await getDashboardAnalytics();
      assert.equal(eventQueries, 1);
      assert.equal(perSessionQueries, 0);
      assert.equal(analytics.metrics.totalAwayTimeSeconds, 90);
      assert.equal(analytics.sessions.find((item) => item.id === 's1')?.awayDurationSeconds, 60);
      assert.equal(analytics.sessions.find((item) => item.id === 's2')?.awayDurationSeconds, 30);
    } finally {
      sessionRepository.getAll = originalGetAll;
      activityEventRepository.listAll = originalListAll;
      activityEventRepository.listBySession = originalListBySession;
    }
  });

  it('sums confirmed elapsed time and averages all persisted statuses', () => {
    const metrics = calculateDashboardMetrics([
      session('s1', 1_200, 'completed'),
      session('s2', 300, 'cancelled'),
      session('s3', 60, 'running'),
      session('s4', 40, 'paused'),
      session('s5', 100, 'interrupted'),
    ], []);
    assert.equal(metrics.totalFocusTimeSeconds, 1_700);
    assert.equal(metrics.sessionCount, 5);
    assert.equal(metrics.averageSessionLengthSeconds, 340);
  });

  it('merges overlapping away intervals and reports unsupported stored metrics as unavailable', () => {
    const metrics = calculateDashboardMetrics([session('s1', 1_000)], [
      away('a1', t0, 100),
      away('a2', t0 + 50_000, 100),
      away('a3', t0 + 200_000, 10, 'another-session'),
    ]);
    assert.equal(metrics.totalAwayTimeSeconds, 160);
    assert.equal(metrics.screenFacingDurationSeconds, null);
    assert.equal(metrics.postureEventCount, null);
    assert.equal(metrics.focusIndicators.length, 1);
    assert.equal(metrics.focusIndicators[0].status, 'calculated');
  });

  it('returns stable zero values for empty data and ignores invalid sessions or events', () => {
    const invalid = { ...session('broken', 10), elapsedSeconds: Number.NaN };
    const malformed = { ...away('bad', t0, 8), duration: Number.NaN };
    const metrics = calculateDashboardMetrics([invalid, session('s1', 0)], [malformed]);
    assert.equal(metrics.totalFocusTimeSeconds, 0);
    assert.equal(metrics.sessionCount, 1);
    assert.equal(metrics.averageSessionLengthSeconds, 0);
    assert.equal(metrics.totalAwayTimeSeconds, 0);
    const empty = calculateDashboardMetrics([], []);
    assert.equal(empty.sessionCount, 0);
    assert.equal(empty.averageSessionLengthSeconds, 0);
    assert.deepEqual(empty.focusIndicators, []);
  });
});
