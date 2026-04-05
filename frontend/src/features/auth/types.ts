export type AuthUser = {
  id: number;
  email: string;
  name: string;
  provider: string;
  profile_image_url?: string | null;
  status: string;
};
