import React, { useState, useEffect } from 'react';
import { ImageOff, Loader2 } from 'lucide-react';
import api from '../services/api';

interface ProtectedImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  caseId?: string;
  imageId?: string;
  src?: string;
  alt: string;
  fallbackIcon?: React.ReactNode;
}

const isDirectUrl = (url?: string): boolean => {
  if (!url) return false;
  return (
    url.startsWith('/uploads/') ||
    url.startsWith('http://') ||
    url.startsWith('https://') ||
    url.startsWith('data:') ||
    url.startsWith('blob:')
  );
};

/**
 * Protected evidence image component.
 * If provided a direct web/local URL (/uploads/..., http/https, data:), displays directly.
 * If provided an S3 canonical key with caseId and imageId, requests a temporary presigned
 * access URL via GET /api/v1/rescues/{caseId}/images/{imageId}/access on demand.
 */
export const ProtectedImage: React.FC<ProtectedImageProps> = ({
  caseId,
  imageId,
  src,
  alt,
  className = 'w-full h-full object-cover',
  fallbackIcon,
  ...rest
}) => {
  const direct = isDirectUrl(src);
  const [presignedUrl, setPresignedUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(!direct && Boolean(caseId && imageId && src));
  const [hasError, setHasError] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;

    if (!src || isDirectUrl(src) || !caseId || !imageId) {
      return;
    }

    api
      .get<{ url: string; expires_in: number }>(`/rescues/${caseId}/images/${imageId}/access`)
      .then((res) => {
        if (isMounted) {
          if (res.data && res.data.url) {
            setPresignedUrl(res.data.url);
          } else {
            setHasError(true);
          }
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setHasError(true);
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [caseId, imageId, src]);

  const displaySrc = direct ? src : presignedUrl;

  if (isLoading) {
    return (
      <div className={`bg-gray-100 flex items-center justify-center text-gray-400 ${className}`}>
        <Loader2 className="w-5 h-5 animate-spin text-brand-teal" />
      </div>
    );
  }

  if (hasError || !displaySrc) {
    return (
      <div className={`bg-gray-100 flex flex-col items-center justify-center text-gray-400 p-2 text-center ${className}`}>
        {fallbackIcon || <ImageOff className="w-6 h-6 mb-1 text-gray-400" />}
        <span className="text-[11px] font-medium text-gray-500">Image unavailable</span>
      </div>
    );
  }

  return (
    <img
      src={displaySrc}
      alt={alt}
      className={className}
      onError={() => setHasError(true)}
      {...rest}
    />
  );
};

export default ProtectedImage;
