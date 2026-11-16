export interface PreviewRendererProps {
  url: string;
  retryWithFreshUrl: () => Promise<string>;
  onError?: () => void;
}
