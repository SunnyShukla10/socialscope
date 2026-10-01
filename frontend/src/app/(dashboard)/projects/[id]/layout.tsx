'use client'
import Link from 'next/link'
import {usePathname,useParams} from 'next/navigation'
export default function ProjectLayout({children}:{children:React.ReactNode}) {
 const {id}=useParams<{id:string}>(); const path=usePathname(); const root=`/projects/${id}`
 return <><nav aria-label="Project sections" className="sticky top-0 z-20 flex gap-1 overflow-x-auto border-b border-border bg-surface px-6 py-2">{[['','Overview'],['/collections','Collections'],['/results','Results'],['/analytics','Analytics'],['/export','Export']].map(([suffix,title])=><Link key={title} href={root+suffix} aria-current={path===root+suffix?'page':undefined} className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm ${path===root+suffix?'bg-primary/10 font-semibold text-primary':'text-text-muted hover:bg-background'}`}>{title}</Link>)}</nav>{children}</>
}
