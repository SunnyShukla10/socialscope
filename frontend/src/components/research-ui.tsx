import React from 'react'
export const field = 'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30'
export const button = 'inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:brightness-110'
export const secondary = 'inline-flex items-center justify-center rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-background disabled:opacity-50'
export function Panel({children,className=''}:{children:React.ReactNode;className?:string}) {return <section className={`rounded-xl border border-border bg-surface p-5 ${className}`}>{children}</section>}
export function ErrorBox({message}:{message:string}) {return message ? <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{message}</div> : null}
