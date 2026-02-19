/**
 * EmailDetail — standalone route wrapper for EmailPane.
 * Reads :id from URL params and renders the full-page reading view.
 */
import { useParams } from 'react-router-dom'
import EmailPane from './EmailPane'

export default function EmailDetail() {
  const { id } = useParams()
  return (
    <div className="max-w-4xl mx-auto">
      <EmailPane emailId={id} />
    </div>
  )
}
