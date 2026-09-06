import JobStatus from '@/components/JobStatus';

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobStatus jobId={id} />;
}
