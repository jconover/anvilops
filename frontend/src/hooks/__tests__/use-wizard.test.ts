import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWizard } from '../use-wizard';

describe('useWizard()', () => {
  describe('initial state', () => {
    it('starts at step 0', () => {
      const { result } = renderHook(() => useWizard(3));
      expect(result.current.currentStep).toBe(0);
    });

    it('reports isFirstStep=true on init', () => {
      const { result } = renderHook(() => useWizard(3));
      expect(result.current.isFirstStep).toBe(true);
    });

    it('reports isLastStep=false on init when totalSteps > 1', () => {
      const { result } = renderHook(() => useWizard(3));
      expect(result.current.isLastStep).toBe(false);
    });

    it('exposes totalSteps', () => {
      const { result } = renderHook(() => useWizard(5));
      expect(result.current.totalSteps).toBe(5);
    });

    it('is both first and last step when totalSteps=1', () => {
      const { result } = renderHook(() => useWizard(1));
      expect(result.current.isFirstStep).toBe(true);
      expect(result.current.isLastStep).toBe(true);
    });
  });

  describe('next()', () => {
    it('advances to the next step', () => {
      const { result } = renderHook(() => useWizard(3));
      act(() => result.current.next());
      expect(result.current.currentStep).toBe(1);
    });

    it('does not advance past the last step', () => {
      const { result } = renderHook(() => useWizard(3));
      act(() => result.current.next());
      act(() => result.current.next());
      act(() => result.current.next()); // clamped at 2
      expect(result.current.currentStep).toBe(2);
    });

    it('sets isLastStep=true when on the final step', () => {
      const { result } = renderHook(() => useWizard(2));
      act(() => result.current.next());
      expect(result.current.isLastStep).toBe(true);
    });

    it('clears isFirstStep after the first next()', () => {
      const { result } = renderHook(() => useWizard(3));
      act(() => result.current.next());
      expect(result.current.isFirstStep).toBe(false);
    });
  });

  describe('previous()', () => {
    it('goes back one step', () => {
      const { result } = renderHook(() => useWizard(3));
      act(() => result.current.next());
      act(() => result.current.previous());
      expect(result.current.currentStep).toBe(0);
    });

    it('does not go below step 0', () => {
      const { result } = renderHook(() => useWizard(3));
      act(() => result.current.previous()); // already at 0
      expect(result.current.currentStep).toBe(0);
    });

    it('restores isFirstStep=true when back at step 0', () => {
      const { result } = renderHook(() => useWizard(3));
      act(() => result.current.next());
      act(() => result.current.previous());
      expect(result.current.isFirstStep).toBe(true);
    });
  });

  describe('goToStep()', () => {
    it('jumps to the specified step', () => {
      const { result } = renderHook(() => useWizard(5));
      act(() => result.current.goToStep(3));
      expect(result.current.currentStep).toBe(3);
    });

    it('ignores negative step values', () => {
      const { result } = renderHook(() => useWizard(5));
      act(() => result.current.goToStep(-1));
      expect(result.current.currentStep).toBe(0);
    });

    it('ignores step values >= totalSteps', () => {
      const { result } = renderHook(() => useWizard(3));
      act(() => result.current.goToStep(3));  // out of bounds (0-2)
      expect(result.current.currentStep).toBe(0);
    });

    it('correctly sets isLastStep when jumping to last step', () => {
      const { result } = renderHook(() => useWizard(4));
      act(() => result.current.goToStep(3));
      expect(result.current.isLastStep).toBe(true);
    });

    it('correctly sets isFirstStep when jumping to step 0', () => {
      const { result } = renderHook(() => useWizard(4));
      act(() => result.current.goToStep(2));
      act(() => result.current.goToStep(0));
      expect(result.current.isFirstStep).toBe(true);
    });
  });
});
