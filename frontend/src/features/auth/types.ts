export type AuthUser = {
  id: number;
  email: string;
  name: string;
  provider?: string;
  student_id?: string | null;
  department?: string | null;
  profile_image_url?: string | null;
  status?: string;
  last_login_at?: string | null;
  created_at?: string;
  updated_at?: string;
};
