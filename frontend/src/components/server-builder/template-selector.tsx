'use client';

import {
  Globe,
  Earth,
  Database,
  Box,
  Coffee,
  Monitor,
  Plus,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SERVER_TEMPLATES, type ServerTemplate } from '@/lib/templates';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Icon resolver -- maps the string icon name from the template to a component
// ---------------------------------------------------------------------------

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Globe,
  Earth,
  Database,
  Box,
  Coffee,
  Monitor,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface TemplateSelectorProps {
  onSelectTemplate: (template: ServerTemplate) => void;
  onStartFromScratch: () => void;
  selectedTemplateId?: string;
}

export function TemplateSelector({
  onSelectTemplate,
  onStartFromScratch,
  selectedTemplateId,
}: TemplateSelectorProps) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold">Start with a Template</h3>
        <p className="text-sm text-muted-foreground">
          Choose a pre-configured template to get started quickly, or build from scratch.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SERVER_TEMPLATES.map((template) => {
          const Icon = ICON_MAP[template.icon] ?? Globe;
          const isSelected = selectedTemplateId === template.id;

          return (
            <Card
              key={template.id}
              className={cn(
                'relative cursor-pointer transition-all hover:shadow-md',
                isSelected && 'ring-2 ring-primary',
              )}
              onClick={() => onSelectTemplate(template)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'flex h-10 w-10 items-center justify-center rounded-lg',
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-base">{template.name}</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pb-4">
                <CardDescription className="text-xs leading-relaxed">
                  {template.description}
                </CardDescription>
                <Button
                  variant={isSelected ? 'default' : 'outline'}
                  size="sm"
                  className="mt-3 w-full"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectTemplate(template);
                  }}
                >
                  {isSelected ? 'Selected' : 'Use Template'}
                </Button>
              </CardContent>
            </Card>
          );
        })}

        {/* Start from scratch card */}
        <Card
          className={cn(
            'relative cursor-pointer border-dashed transition-all hover:shadow-md',
            !selectedTemplateId && 'ring-2 ring-primary',
          )}
          onClick={onStartFromScratch}
        >
          <CardHeader className="pb-3">
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-lg',
                  !selectedTemplateId
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                <Plus className="h-5 w-5" />
              </div>
              <CardTitle className="text-base">Start from Scratch</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="pb-4">
            <CardDescription className="text-xs leading-relaxed">
              Configure every option manually. Best when your requirements do not
              match any existing template.
            </CardDescription>
            <Button
              variant={!selectedTemplateId ? 'default' : 'outline'}
              size="sm"
              className="mt-3 w-full"
              onClick={(e) => {
                e.stopPropagation();
                onStartFromScratch();
              }}
            >
              {!selectedTemplateId ? 'Selected' : 'Start Fresh'}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
