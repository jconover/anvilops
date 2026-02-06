'use client';

import { ArrowLeft, ArrowRight, Loader2, Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useWizard } from '@/hooks/use-wizard';
import { useServerForm } from '@/hooks/use-server-form';
import { SERVER_TEMPLATES, type ServerTemplate } from '@/lib/templates';
import { StepIndicator } from './step-indicator';
import { TemplateSelector } from './template-selector';
import { StepEnvironment } from './step-environment';
import { StepInstance } from './step-instance';
import { StepSecurity } from './step-security';
import { StepSoftware } from './step-software';
import { StepReview } from './step-review';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TOTAL_STEPS = 5;

const STEP_TITLES = [
  'Environment & OS',
  'Instance Configuration',
  'Security & Networking',
  'Software & Configuration',
  'Review & Submit',
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface WizardLayoutProps {
  /** Called when the user submits the form. */
  onSubmit: () => void;
  /** True while the create mutation is in flight. */
  isSubmitting: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function WizardLayout({ onSubmit, isSubmitting }: WizardLayoutProps) {
  const wizard = useWizard(TOTAL_STEPS);
  const template_id = useServerForm((s) => s.template_id);
  const applyTemplate = useServerForm((s) => s.applyTemplate);
  const reset = useServerForm((s) => s.reset);

  // Template handlers
  const handleSelectTemplate = (template: ServerTemplate) => {
    applyTemplate(template);
  };

  const handleStartFromScratch = () => {
    reset();
  };

  // Render current step content
  const renderStep = () => {
    switch (wizard.currentStep) {
      case 0:
        return <StepEnvironment />;
      case 1:
        return <StepInstance />;
      case 2:
        return <StepSecurity />;
      case 3:
        return <StepSoftware />;
      case 4:
        return <StepReview onGoToStep={wizard.goToStep} />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Template selector -- shown only on Step 0 */}
      {wizard.currentStep === 0 && (
        <>
          <TemplateSelector
            onSelectTemplate={handleSelectTemplate}
            onStartFromScratch={handleStartFromScratch}
            selectedTemplateId={template_id}
          />
          <Separator />
        </>
      )}

      {/* Main wizard area */}
      <div className="flex flex-col gap-8 lg:flex-row">
        {/* Left sidebar -- step indicator */}
        <aside className="w-full shrink-0 lg:w-64">
          <StepIndicator
            currentStep={wizard.currentStep}
            onStepClick={wizard.goToStep}
          />
        </aside>

        {/* Right content area */}
        <div className="min-w-0 flex-1">
          {/* Step heading */}
          <div className="mb-6">
            <h2 className="text-xl font-semibold tracking-tight">
              {STEP_TITLES[wizard.currentStep]}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Step {wizard.currentStep + 1} of {TOTAL_STEPS}
            </p>
          </div>

          {/* Step content */}
          <div className="min-h-[24rem]">{renderStep()}</div>

          {/* Navigation buttons */}
          <div className="mt-8 flex items-center justify-between border-t pt-6">
            <Button
              variant="outline"
              onClick={wizard.previous}
              disabled={wizard.isFirstStep}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Previous
            </Button>

            {wizard.isLastStep ? (
              <Button onClick={onSubmit} disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  <>
                    <Rocket className="mr-2 h-4 w-4" />
                    Submit Build Request
                  </>
                )}
              </Button>
            ) : (
              <Button onClick={wizard.next}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
