'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { ArrowLeft } from 'lucide-react'

interface ProjectBackButtonProps {
  projectId?: string
}

export function ProjectBackButton({ projectId }: ProjectBackButtonProps) {
  const router = useRouter()

  function handleBack() {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back()
      return
    }

    router.push(projectId ? `/projects/${projectId}` : '/projects')
  }

  return (
    <Button type="button" variant="outline" size="sm" onClick={handleBack}>
      <ArrowLeft size={14} />
      Back
    </Button>
  )
}
