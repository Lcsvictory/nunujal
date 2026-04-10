import { useEffect, useId, useState, type MouseEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

type OverlayProps = {
  open: boolean;
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
};

export function Overlay({
  open,
  title,
  description,
  onClose,
  children,
}: OverlayProps) {
  const titleId = useId();
  const descriptionId = useId();
  const [container, setContainer] = useState<Element | null>(null);

  useEffect(() => {
    const updateContainer = () => {
      setContainer(document.fullscreenElement || document.body);
    };
    updateContainer();
    document.addEventListener("fullscreenchange", updateContainer);
    return () => {
      document.removeEventListener("fullscreenchange", updateContainer);
    };
  }, []);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose, open]);

  if (!open || !container) {
    return null;
  }

  const handleBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return createPortal(
    <div className="overlay-backdrop" onMouseDown={handleBackdropClick}>
      <section
        className="overlay-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
      >
        <header className="overlay-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            <p id={descriptionId}>{description}</p>
          </div>
          <button
            type="button"
            className="button button-ghost button-square"
            onClick={onClose}
            aria-label="오버레이 닫기"
          >
            ×
          </button>
        </header>
        <div className="overlay-body">{children}</div>
      </section>
    </div>,
    container,
  );
}
