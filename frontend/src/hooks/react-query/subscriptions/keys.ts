import { createQueryKeys } from '@/hooks/use-query';

export const subscriptionKeys = createQueryKeys({
  all: ['subscription'] as const,
  details: () => [...subscriptionKeys.all, 'details'] as const,
});

export const modelKeys = createQueryKeys({
  all: ['models'] as const,
  available: ['models', 'available'] as const,
});

export const usageKeys = createQueryKeys({
  all: ['usage'] as const,
  logs: (page?: number, itemsPerPage?: number) => [...usageKeys.all, 'logs', { page, itemsPerPage }] as const,
});