// Central branding config. The product name is read from NEXT_PUBLIC_APP_NAME
// (baked at build time) so a deployment can rebrand without code changes.
// APP_URL is the public app origin used for absolute links in copy/embeds;
// empty means "use the current origin".
export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || "EasyTech";
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "";
