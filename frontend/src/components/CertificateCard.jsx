import { motion } from 'framer-motion';
import { Award, Download, Lock } from 'lucide-react';
import { jsPDF } from 'jspdf';
import { Button } from '@/components/ui/button';

/**
 * CertificateCard — shows a certificate's progress, and once earned, renders
 * a preview plus a "Download PDF" button that draws the certificate with
 * jsPDF (pure vector — no external fonts/images, so it's fully offline-safe).
 */
const downloadCertificatePdf = (cert) => {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
  const w = doc.internal.pageSize.getWidth();
  const h = doc.internal.pageSize.getHeight();
  const navy = [15, 23, 42];
  const teal = [47, 191, 174];

  // Border
  doc.setDrawColor(...teal);
  doc.setLineWidth(2);
  doc.rect(24, 24, w - 48, h - 48);
  doc.setDrawColor(...navy);
  doc.setLineWidth(0.75);
  doc.rect(34, 34, w - 68, h - 68);

  // Header
  doc.setTextColor(...teal);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.text('TRAUMA TRANSFORMATION INSTITUTE', w / 2, 90, { align: 'center' });

  doc.setTextColor(...navy);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'normal');
  doc.text('Certificate of Completion', w / 2, 118, { align: 'center' });

  doc.setFont('times', 'bolditalic');
  doc.setFontSize(34);
  doc.text(cert.title, w / 2, 165, { align: 'center' });

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(13);
  doc.text('This certifies that', w / 2, 205, { align: 'center' });

  doc.setFont('times', 'bold');
  doc.setFontSize(30);
  doc.text(cert.recipient_name, w / 2, 245, { align: 'center' });

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(13);
  doc.text('has successfully completed all required coursework and assessments', w / 2, 280, { align: 'center' });
  doc.text('for this program with the Trauma Transformation Institute.', w / 2, 298, { align: 'center' });

  // Divider
  doc.setDrawColor(...teal);
  doc.setLineWidth(1);
  doc.line(w / 2 - 90, 320, w / 2 + 90, 320);

  const issuedDate = new Date(cert.issued_at).toLocaleDateString('en-IN', {
    year: 'numeric', month: 'long', day: 'numeric'
  });

  doc.setFontSize(10);
  doc.setTextColor(100, 116, 139);
  doc.text(`Issued ${issuedDate}`, w / 2 - 140, 355, { align: 'center' });
  doc.text(`Certificate No. ${cert.certificate_number}`, w / 2 + 140, 355, { align: 'center' });

  doc.save(`${cert.title.replace(/\s+/g, '_')}_${cert.certificate_number}.pdf`);
};

const CertificateCard = ({ title, completed, progress, certificate }) => {
  const pct = progress.total ? Math.round((progress.done / progress.total) * 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-2xl border p-6 ${
        completed ? 'border-amber-200 bg-gradient-to-br from-amber-50 to-white' : 'border-slate-200 bg-white'
      }`}
      data-testid={`certificate-card-${certificate?.track || title}`}
    >
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 ${completed ? 'bg-amber-400' : 'bg-slate-100'}`}>
          {completed ? <Award className="w-6 h-6 text-white" /> : <Lock className="w-5 h-5 text-slate-400" />}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="font-playfair font-semibold text-navy-900 mb-1">{title}</h4>
          {completed ? (
            <>
              <p className="font-dm-sans text-xs text-navy-400 mb-3">
                Certificate No. {certificate.certificate_number} · Issued{' '}
                {new Date(certificate.issued_at).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' })}
              </p>
              <Button
                size="sm"
                onClick={() => downloadCertificatePdf(certificate)}
                className="bg-amber-500 hover:bg-amber-500/90 font-dm-sans rounded-lg"
                data-testid={`download-certificate-${certificate.track}`}
              >
                <Download className="w-4 h-4 mr-2" /> Download PDF
              </Button>
            </>
          ) : (
            <>
              <p className="font-dm-sans text-sm text-navy-500 mb-3">
                {progress.done} of {progress.total} courses completed (enrolled + quiz passed at 90%+)
              </p>
              <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                <motion.div
                  className="h-full bg-teal rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.6 }}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default CertificateCard;
