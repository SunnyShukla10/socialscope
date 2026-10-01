import { fetchApi } from './api'
export { fetchApi }
export const platforms = ['instagram','tiktok','facebook','twitter','reddit','youtube']
export const label = (p: string) => p === 'twitter' ? 'X / Twitter' : p.charAt(0).toUpperCase()+p.slice(1)
export const active = (s: string) => ['pending','queued','running','cancelling'].includes(s)
export const dateLabel = (s?: string) => s ? new Date(s).toLocaleString() : 'Not supplied'
export const errorMessage = (e: unknown) => e && typeof e === 'object' && 'message' in e ? String(e.message) : 'Request failed. Check the API and try again.'
export interface Usage { comparison_limit:number; comparison_remaining:number; request_limit_per_platform:number; platforms:Record<string,{requests:number;reserved:number;estimated:number;reported:number;unknown_requests:number;charged_allowance:number;credit_limit?:number;credits_bounded:boolean}> }
export interface Run { id:string; pull_id:string; mode:string; name:string; status:string; platforms:string[]; date_from?:string; date_to?:string; requested_post_count:number; total_posts_collected:number; platform_allocations:Record<string,number>; platform_states:Record<string,{status:string;posts_collected:number;error?:string;provider_stop_reason?:string;provider_stop_details?:Record<string,unknown>}>; query_versions:{boolean_query:string}[]; usage:Usage; created_at:string; completed_at?:string; error_message?:string; preview_examples:{id:string;platform:string;body:string;url?:string;published_at?:string}[] }
export interface SourceInfo { version:string;build:string;account_limit_warning:string;sources:{platform:string;provider:string;configured:boolean;comparison:boolean;limitations:string}[] }
