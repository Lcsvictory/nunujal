export type AuthUser = {
  id: number;
  email: string;
  name: string;
  provider: string;
  department?: string | null;
  profile_image_url?: string | null;
  status: string;
};
