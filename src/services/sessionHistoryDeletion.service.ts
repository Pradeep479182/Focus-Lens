import { SessionRepository, dbService, sessionRepository } from './db.service.ts';

export interface DeletionResult {
  success: true;
  deletedSessionsCount: number;
  error?: never;
}

export interface DeletionError {
  success: false;
  deletedSessionsCount: 0;
  error: string;
}

export type SessionHistoryDeletionResult = DeletionResult | DeletionError;

/**
 * Service responsible for deleting stored session history from the local SQLite database.
 * 
 * This service provides methods to clear all session-history records while preserving
 * user preferences and privacy settings. It leverages the database schema's CASCADE
 * relationship to automatically delete activity events when their parent sessions are deleted.
 * 
 * Key behaviors:
 * - Deletes all sessions and their associated activity events via CASCADE
 * - Preserves user_preferences and privacy_settings tables
 * - Uses database transactions to ensure atomicity
 * - Handles empty databases gracefully
 * - Provides both Promise-based and safe result-wrapped methods for UI compatibility
 */
export class SessionHistoryDeletionService {
  private readonly sessionRepository: SessionRepository;
  private readonly database: typeof dbService;

  constructor(
    sessionRepositoryArg: SessionRepository,
    databaseArg: typeof dbService,
  ) {
    this.sessionRepository = sessionRepositoryArg;
    this.database = databaseArg;
  }

  /**
   * Delete all session history from the local database.
   * 
   * This operation:
   * - Deletes all records from the sessions table
   * - Automatically deletes all activity_events via the CASCADE foreign key
   * - Preserves user_preferences and privacy_settings tables
   * - Uses a database transaction to ensure atomicity
   * 
   * @returns The number of sessions deleted
   * @throws Error if the database operation fails
   */
  async deleteAllSessionHistory(): Promise<number> {
    const deletedCount = await this.sessionRepository.count();
    
    if (deletedCount === 0) {
      return 0;
    }

    try {
      // Use a transaction to ensure atomic deletion
      await this.database.execute('BEGIN IMMEDIATE');
      
      try {
        // Delete all sessions - activity_events will be deleted via CASCADE
        const result = await this.database.execute('DELETE FROM sessions');
        
        await this.database.execute('COMMIT');
        
        return result.rowsAffected;
      } catch (error) {
        await this.database.execute('ROLLBACK');
        throw error;
      }
    } catch (error) {
      throw new Error('Unable to delete session history.', { cause: error });
    }
  }

  /**
   * Safe deletion method that returns a typed result object and never throws.
   * This is designed for UI components to handle deletion errors gracefully.
   * 
   * @returns A result object indicating success/failure, the count of deleted sessions,
   *          and an error message if the operation failed
   */
  async deleteAllSessionHistoryResult(): Promise<SessionHistoryDeletionResult> {
    try {
      const deletedSessionsCount = await this.deleteAllSessionHistory();
      return { success: true, deletedSessionsCount };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete session history.';
      return { success: false, deletedSessionsCount: 0, error: message };
    }
  }

  /**
   * Check whether any session history exists in the database.
   * 
   * @returns true if at least one session exists, false otherwise
   */
  async hasSessionHistory(): Promise<boolean> {
    const count = await this.sessionRepository.count();
    return count > 0;
  }

  /**
   * Get the total count of sessions in the database.
   * 
   * @returns The number of sessions stored
   */
  async getSessionHistoryCount(): Promise<number> {
    return this.sessionRepository.count();
  }
}

// Lazy initialization to avoid circular reference issues
let _sessionHistoryDeletionService: SessionHistoryDeletionService | null = null;

export function getSessionHistoryDeletionService(): SessionHistoryDeletionService {
  if (!_sessionHistoryDeletionService) {
    _sessionHistoryDeletionService = new SessionHistoryDeletionService(
      sessionRepository,
      dbService,
    );
  }
  return _sessionHistoryDeletionService;
}
