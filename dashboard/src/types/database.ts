export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

type ProfilesRow = {
  id: string;
  role: "parent" | "child";
  display_name: string;
  created_at: string;
};

type ChildrenRow = {
  id: string;
  parent_id: string;
  display_name: string;
  created_at: string;
};

type DevicesRow = {
  id: string;
  child_id: string;
  label: string;
  api_key_hash: string | null;
  created_at: string;
};

type SessionsRow = {
  id: string;
  child_id: string;
  started_at: string;
  ended_at: string | null;
  turn_count: number;
  primary_mode: string;
  topic: string | null;
  duration_seconds: number | null;
};

type TurnsRow = {
  id: string;
  session_id: string;
  idx: number;
  role: "user" | "assistant";
  content: string;
  mode: string | null;
  phase: string | null;
  tool: string | null;
  topic: string | null;
  created_at: string;
};

type MasteryScoresRow = {
  child_id: string;
  topic: string;
  score: number;
  updated_at: string;
};

type MasteryEventsRow = {
  id: string;
  child_id: string;
  session_id: string | null;
  event: string;
  topic: string;
  score: number | null;
  created_at: string;
};

type ChildStatsRow = {
  child_id: string;
  current_streak_days: number;
  longest_streak_days: number;
  sessions_completed: number;
  last_session_on: string | null;
};

type SessionStatsRow = {
  id: string;
  session_id: string;
  child_id: string;
  mood_counts: Record<string, number>;
  problems_solved: number;
  subjects: Record<string, number>;
  topics_needing_help: Record<string, boolean>;
  week_of: string;
  created_at: string;
};

type EmergencyStopsRow = {
  id: string;
  child_id: string;
  session_id: string | null;
  transcript: string;
  triggered_at: string;
};

export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: ProfilesRow;
        Insert: {
          id: string;
          role?: "parent" | "child";
          display_name?: string;
          created_at?: string;
        };
        Update: Partial<ProfilesRow>;
        Relationships: [];
      };
      children: {
        Row: ChildrenRow;
        Insert: {
          id?: string;
          parent_id: string;
          display_name: string;
          created_at?: string;
        };
        Update: Partial<ChildrenRow>;
        Relationships: [
          {
            foreignKeyName: "children_parent_id_fkey";
            columns: ["parent_id"];
            isOneToOne: false;
            referencedRelation: "profiles";
            referencedColumns: ["id"];
          },
        ];
      };
      devices: {
        Row: DevicesRow;
        Insert: {
          id?: string;
          child_id: string;
          label?: string;
          api_key_hash?: string | null;
          created_at?: string;
        };
        Update: Partial<DevicesRow>;
        Relationships: [
          {
            foreignKeyName: "devices_child_id_fkey";
            columns: ["child_id"];
            isOneToOne: false;
            referencedRelation: "children";
            referencedColumns: ["id"];
          },
        ];
      };
      sessions: {
        Row: SessionsRow;
        Insert: {
          id?: string;
          child_id: string;
          started_at?: string;
          ended_at?: string | null;
          turn_count?: number;
          primary_mode?: string;
          topic?: string | null;
          duration_seconds?: number | null;
        };
        Update: Partial<SessionsRow>;
        Relationships: [
          {
            foreignKeyName: "sessions_child_id_fkey";
            columns: ["child_id"];
            isOneToOne: false;
            referencedRelation: "children";
            referencedColumns: ["id"];
          },
        ];
      };
      turns: {
        Row: TurnsRow;
        Insert: {
          id?: string;
          session_id: string;
          idx: number;
          role: "user" | "assistant";
          content?: string;
          mode?: string | null;
          phase?: string | null;
          tool?: string | null;
          topic?: string | null;
          created_at?: string;
        };
        Update: Partial<TurnsRow>;
        Relationships: [
          {
            foreignKeyName: "turns_session_id_fkey";
            columns: ["session_id"];
            isOneToOne: false;
            referencedRelation: "sessions";
            referencedColumns: ["id"];
          },
        ];
      };
      mastery_scores: {
        Row: MasteryScoresRow;
        Insert: {
          child_id: string;
          topic: string;
          score?: number;
          updated_at?: string;
        };
        Update: Partial<MasteryScoresRow>;
        Relationships: [
          {
            foreignKeyName: "mastery_scores_child_id_fkey";
            columns: ["child_id"];
            isOneToOne: false;
            referencedRelation: "children";
            referencedColumns: ["id"];
          },
        ];
      };
      mastery_events: {
        Row: MasteryEventsRow;
        Insert: {
          id?: string;
          child_id: string;
          session_id?: string | null;
          event: string;
          topic: string;
          score?: number | null;
          created_at?: string;
        };
        Update: Partial<MasteryEventsRow>;
        Relationships: [
          {
            foreignKeyName: "mastery_events_child_id_fkey";
            columns: ["child_id"];
            isOneToOne: false;
            referencedRelation: "children";
            referencedColumns: ["id"];
          },
        ];
      };
      session_stats: {
        Row: SessionStatsRow;
        Insert: {
          id?: string;
          session_id: string;
          child_id: string;
          mood_counts?: Record<string, number>;
          problems_solved?: number;
          subjects?: Record<string, number>;
          topics_needing_help?: Record<string, boolean>;
          week_of: string;
          created_at?: string;
        };
        Update: Partial<SessionStatsRow>;
        Relationships: [];
      };
      emergency_stops: {
        Row: EmergencyStopsRow;
        Insert: {
          id?: string;
          child_id: string;
          session_id?: string | null;
          transcript?: string;
          triggered_at?: string;
        };
        Update: Partial<EmergencyStopsRow>;
        Relationships: [];
      };
      child_stats: {
        Row: ChildStatsRow;
        Insert: {
          child_id: string;
          current_streak_days?: number;
          longest_streak_days?: number;
          sessions_completed?: number;
          last_session_on?: string | null;
        };
        Update: Partial<ChildStatsRow>;
        Relationships: [
          {
            foreignKeyName: "child_stats_child_id_fkey";
            columns: ["child_id"];
            isOneToOne: true;
            referencedRelation: "children";
            referencedColumns: ["id"];
          },
        ];
      };
    };
    Views: Record<string, never>;
    Functions: {
      parent_owns_child: {
        Args: { cid: string };
        Returns: boolean;
      };
      delete_child_data: {
        Args: { cid: string };
        Returns: void;
      };
    };
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
};
