'use client';

import { SectionHeader } from '@/components/home/section-header';
import type { PricingTier } from '@/lib/home';
import { siteConfig } from '@/lib/home';
import { cn } from '@/lib/utils';
import { motion } from 'motion/react';
import React, { useState, useEffect } from 'react';
import { CheckIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  createCheckoutSession,
  SubscriptionStatus,
  CreateCheckoutSessionResponse,
} from '@/lib/api';
import { toast } from 'sonner';
import { isLocalMode } from '@/lib/config';
import { useSubscription } from '@/hooks/react-query';

// Constants
export const SUBSCRIPTION_PLANS = {
  FREE: 'free',
  PRO: 'base',
  ENTERPRISE: 'extra',
};

// Types
type ButtonVariant =
  | 'default'
  | 'secondary'
  | 'ghost'
  | 'outline'
  | 'link'
  | null;

interface PricingTabsProps {
  activeTab: 'cloud' | 'self-hosted';
  setActiveTab: (tab: 'cloud' | 'self-hosted') => void;
  className?: string;
}

interface PriceDisplayProps {
  price: string;
  isCompact?: boolean;
}

interface PricingTierProps {
  tier: PricingTier;
  isCompact?: boolean;
  currentSubscription: SubscriptionStatus | null;
  isLoading: Record<string, boolean>;
  isFetchingPlan: boolean;
  selectedPlan?: string;
  onPlanSelect?: (planId: string) => void;
  onSubscriptionUpdate?: () => void;
  isAuthenticated?: boolean;
  returnUrl: string;
  insideDialog?: boolean;
  billingPeriod?: 'monthly' | 'yearly';
}

// Components
function PricingTabs({ activeTab, setActiveTab, className }: PricingTabsProps) {
  return (
    <div
      className={cn(
        'relative flex w-fit items-center rounded-full border p-0.5 backdrop-blur-sm cursor-pointer h-9 flex-row bg-muted',
        className,
      )}
    >
      {['cloud', 'self-hosted'].map((tab) => (
        <button
          key={tab}
          onClick={() => setActiveTab(tab as 'cloud' | 'self-hosted')}
          className={cn(
            'relative z-[1] px-3 h-8 flex items-center justify-center cursor-pointer',
            {
              'z-0': activeTab === tab,
            },
          )}
        >
          {activeTab === tab && (
            <motion.div
              layoutId="active-tab"
              className="absolute inset-0 rounded-full bg-white dark:bg-[#3F3F46] shadow-md border border-border"
              transition={{
                duration: 0.2,
                type: 'spring',
                stiffness: 300,
                damping: 25,
                velocity: 2,
              }}
            />
          )}
          <span
            className={cn(
              'relative block text-sm font-medium duration-200 shrink-0',
              activeTab === tab ? 'text-primary' : 'text-muted-foreground',
            )}
          >
            {tab === 'cloud' ? 'Cloud' : 'Self-hosted'}
          </span>
        </button>
      ))}
    </div>
  );
}

function PriceDisplay({ price, isCompact }: PriceDisplayProps) {
  return (
    <motion.span
      key={price}
      className={isCompact ? 'text-xl font-semibold' : 'text-4xl font-semibold'}
      initial={{
        opacity: 0,
        x: 10,
        filter: 'blur(5px)',
      }}
      animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
    >
      {price}
    </motion.span>
  );
}

function BillingPeriodToggle({ 
  billingPeriod, 
  setBillingPeriod 
}: { 
  billingPeriod: 'monthly' | 'yearly';
  setBillingPeriod: (period: 'monthly' | 'yearly') => void;
}) {
  return (
    <div className="flex items-center justify-center gap-3">
      <div 
        className="relative bg-muted rounded-full p-1 cursor-pointer"
        onClick={() => setBillingPeriod(billingPeriod === 'monthly' ? 'yearly' : 'monthly')}
      >
        <div className="flex">
          <div className={cn("px-3 py-1 rounded-full text-xs font-medium transition-all duration-200", 
            billingPeriod === 'monthly' 
              ? 'bg-background text-foreground shadow-sm' 
              : 'text-muted-foreground'
          )}>
            Monthly
          </div>
          <div className={cn("px-3 py-1 rounded-full text-xs font-medium transition-all duration-200 flex items-center gap-1", 
            billingPeriod === 'yearly' 
              ? 'bg-background text-foreground shadow-sm' 
              : 'text-muted-foreground'
          )}>
            Yearly
            <span className="bg-green-600 text-green-50 dark:bg-green-500 dark:text-green-50 text-[10px] px-1.5 py-0.5 rounded-full font-semibold whitespace-nowrap">
              15% off
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function PricingTier({
  tier,
  isCompact = false,
  currentSubscription,
  isLoading,
  isFetchingPlan,
  selectedPlan,
  onPlanSelect,
  onSubscriptionUpdate,
  isAuthenticated = false,
  returnUrl,
  insideDialog = false,
  billingPeriod = 'monthly',
}: PricingTierProps) {
  // Auto-select the correct plan only on initial load - simplified since no more Custom tier
  const handleSubscribe = async (planStripePriceId: string) => {
    if (!isAuthenticated) {
      window.location.href = '/auth?mode=signup';
      return;
    }

    if (isLoading[planStripePriceId]) {
      return;
    }

    try {
      onPlanSelect?.(planStripePriceId);

      const response: CreateCheckoutSessionResponse =
        await createCheckoutSession({
          price_id: planStripePriceId,
          success_url: returnUrl,
          cancel_url: returnUrl,
        });

      console.log('Subscription action response:', response);

      switch (response.status) {
        case 'new':
        case 'checkout_created':
          if (response.url) {
            window.location.href = response.url;
          } else {
            console.error(
              "Error: Received status 'checkout_created' but no checkout URL.",
            );
            toast.error('Failed to initiate subscription. Please try again.');
          }
          break;
        case 'upgraded':
        case 'updated':
          const upgradeMessage = response.details?.is_upgrade
            ? `Subscription upgraded from $${response.details.current_price} to $${response.details.new_price}`
            : 'Subscription updated successfully';
          toast.success(upgradeMessage);
          if (onSubscriptionUpdate) onSubscriptionUpdate();
          break;
        case 'downgrade_scheduled':
        case 'scheduled':
          const effectiveDate = response.effective_date
            ? new Date(response.effective_date).toLocaleDateString()
            : 'the end of your billing period';

          const statusChangeMessage = 'Subscription change scheduled';

          toast.success(
            <div>
              <p>{statusChangeMessage}</p>
              <p className="text-sm mt-1">
                Your plan will change on {effectiveDate}.
              </p>
            </div>,
          );
          if (onSubscriptionUpdate) onSubscriptionUpdate();
          break;
        case 'no_change':
          toast.info(response.message || 'You are already on this plan.');
          break;
        default:
          console.warn(
            'Received unexpected status from createCheckoutSession:',
            response.status,
          );
          toast.error('An unexpected error occurred. Please try again.');
      }
    } catch (error: any) {
      console.error('Error processing subscription:', error);
      const errorMessage =
        error?.response?.data?.detail ||
        error?.message ||
        'Failed to process subscription. Please try again.';
      toast.error(errorMessage);
    }
  };

  const tierPriceId = billingPeriod === 'yearly' && tier.yearlyStripePriceId 
    ? tier.yearlyStripePriceId 
    : tier.stripePriceId;
  const displayPrice = billingPeriod === 'yearly' && tier.yearlyPrice 
    ? tier.yearlyPrice 
    : tier.price;
  
  // Find the current tier (moved outside conditional for JSX access)
  const currentTier = siteConfig.cloudPricingItems.find(
    (p) => p.stripePriceId === currentSubscription?.price_id || p.yearlyStripePriceId === currentSubscription?.price_id,
  );
  
  const isCurrentActivePlan =
    isAuthenticated && currentSubscription?.price_id === tierPriceId;
  const isScheduled = isAuthenticated && currentSubscription?.has_schedule;
  const isScheduledTargetPlan =
    isScheduled && currentSubscription?.scheduled_price_id === tierPriceId;
  const isPlanLoading = isLoading[tierPriceId];

  let buttonText = isAuthenticated ? 'Select Plan' : 'Start Free';
  let buttonDisabled = isPlanLoading;
  let buttonVariant: ButtonVariant = null;
  let ringClass = '';
  let statusBadge = null;
  let buttonClassName = '';

  if (isAuthenticated) {
    if (isCurrentActivePlan) {
      buttonText = 'Current Plan';
      buttonDisabled = true;
      buttonVariant = 'secondary';
      ringClass = isCompact ? 'ring-1 ring-primary' : 'ring-2 ring-primary';
      buttonClassName = 'bg-primary/5 hover:bg-primary/10 text-primary';
      statusBadge = (
        <span className="bg-primary/10 text-primary text-[10px] font-medium px-1.5 py-0.5 rounded-full">
          Current
        </span>
      );
    } else if (isScheduledTargetPlan) {
      buttonText = 'Scheduled';
      buttonDisabled = true;
      buttonVariant = 'outline';
      ringClass = isCompact
        ? 'ring-1 ring-yellow-500'
        : 'ring-2 ring-yellow-500';
      buttonClassName =
        'bg-yellow-500/5 hover:bg-yellow-500/10 text-yellow-600 border-yellow-500/20';
      statusBadge = (
        <span className="bg-yellow-500/10 text-yellow-600 text-[10px] font-medium px-1.5 py-0.5 rounded-full">
          Scheduled
        </span>
      );
    } else if (isScheduled && currentSubscription?.price_id === tierPriceId) {
      buttonText = 'Change Scheduled';
      buttonVariant = 'secondary';
      ringClass = isCompact ? 'ring-1 ring-primary' : 'ring-2 ring-primary';
      buttonClassName = 'bg-primary/5 hover:bg-primary/10 text-primary';
      statusBadge = (
        <span className="bg-yellow-500/10 text-yellow-600 text-[10px] font-medium px-1.5 py-0.5 rounded-full">
          Downgrade Pending
        </span>
      );
    } else {
      const currentPriceString = currentSubscription
        ? currentTier?.price || '$0'
        : '$0';
      const selectedPriceString = tier.price;
      const currentAmount =
        currentPriceString === '$0'
          ? 0
          : parseFloat(currentPriceString.replace(/[^\d.]/g, '') || '0') * 100;
      const targetAmount =
        selectedPriceString === '$0'
          ? 0
          : parseFloat(selectedPriceString.replace(/[^\d.]/g, '') || '0') * 100;

      // Check if current subscription is monthly and target is yearly for same tier
      const currentIsMonthly = currentTier && currentSubscription?.price_id === currentTier.stripePriceId;
      const currentIsYearly = currentTier && currentSubscription?.price_id === currentTier.yearlyStripePriceId;
      const targetIsMonthly = tier.stripePriceId === tierPriceId;
      const targetIsYearly = tier.yearlyStripePriceId === tierPriceId;
      const isSameTierDifferentBilling = currentTier && currentTier.name === tier.name && 
        ((currentIsMonthly && targetIsYearly) || (currentIsYearly && targetIsMonthly));

      if (
        currentAmount === 0 &&
        targetAmount === 0 &&
        currentSubscription?.status !== 'no_subscription'
      ) {
        buttonText = 'Select Plan';
        buttonDisabled = true;
        buttonVariant = 'secondary';
        buttonClassName = 'bg-primary/5 hover:bg-primary/10 text-primary';
      } else {
        if (targetAmount > currentAmount || (currentIsMonthly && targetIsYearly && targetAmount >= currentAmount)) {
          // Allow upgrade to higher tier OR switch from monthly to yearly at same/higher tier
          // But prevent yearly to monthly switches even if target amount is higher
          if (currentIsYearly && targetIsMonthly) {
            buttonText = '-';
            buttonDisabled = true;
            buttonVariant = 'secondary';
            buttonClassName =
              'opacity-50 cursor-not-allowed bg-muted text-muted-foreground';
          } else if (currentIsMonthly && targetIsYearly && targetAmount === currentAmount) {
            buttonText = 'Switch to Yearly';
            buttonVariant = 'default';
            buttonClassName = 'bg-green-600 hover:bg-green-700 text-white';
          } else {
            buttonText = 'Upgrade';
            buttonVariant = tier.buttonColor as ButtonVariant;
            buttonClassName = 'bg-primary hover:bg-primary/90 text-primary-foreground';
          }
        } else if (targetAmount < currentAmount && !(currentIsYearly && targetIsMonthly && targetAmount === currentAmount)) {
          buttonText = '-';
          buttonDisabled = true;
          buttonVariant = 'secondary';
          buttonClassName =
            'opacity-50 cursor-not-allowed bg-muted text-muted-foreground';
        } else if (isSameTierDifferentBilling) {
          // Allow switching between monthly and yearly for same tier
          if (currentIsMonthly && targetIsYearly) {
            buttonText = 'Switch to Yearly';
            buttonVariant = 'default';
            buttonClassName = 'bg-green-600 hover:bg-green-700 text-white';
          } else if (currentIsYearly && targetIsMonthly) {
            // Prevent downgrade from yearly to monthly
            buttonText = '-';
            buttonDisabled = true;
            buttonVariant = 'secondary';
            buttonClassName =
              'opacity-50 cursor-not-allowed bg-muted text-muted-foreground';
          } else {
            buttonText = 'Select Plan';
            buttonVariant = tier.buttonColor as ButtonVariant;
            buttonClassName =
              'bg-primary hover:bg-primary/90 text-primary-foreground';
          }
        } else {
          buttonText = 'Select Plan';
          buttonVariant = tier.buttonColor as ButtonVariant;
          buttonClassName =
            'bg-primary hover:bg-primary/90 text-primary-foreground';
        }
      }
    }

    if (isPlanLoading) {
      buttonText = 'Loading...';
      buttonClassName = 'opacity-70 cursor-not-allowed';
    }
  } else {
    // Non-authenticated state styling
    buttonVariant = tier.buttonColor as ButtonVariant;
    buttonClassName =
      tier.buttonColor === 'default'
        ? 'bg-primary hover:bg-primary/90 text-white'
        : 'bg-secondary hover:bg-secondary/90 text-white';
  }

  return (
    <div
      className={cn(
        'rounded-xl flex flex-col relative',
        insideDialog 
          ? 'min-h-[420px]' 
          : 'h-full min-h-[480px]',
        tier.isPopular && !insideDialog
          ? 'md:shadow-[0px_61px_24px_-10px_rgba(0,0,0,0.01),0px_34px_20px_-8px_rgba(0,0,0,0.05),0px_15px_15px_-6px_rgba(0,0,0,0.09),0px_4px_8px_-2px_rgba(0,0,0,0.10),0px_0px_0px_1px_rgba(0,0,0,0.08)] bg-accent'
          : 'bg-[#F3F4F6] dark:bg-[#F9FAFB]/[0.02] border border-border',
        !insideDialog && ringClass,
      )}
    >
      <div className={cn(
        "flex flex-col gap-3",
        insideDialog ? "p-3" : "p-4"
      )}>
        <p className="text-sm flex items-center gap-2">
          {tier.name}
          {tier.isPopular && (
            <span className="bg-gradient-to-b from-secondary/50 from-[1.92%] to-secondary to-[100%] text-white inline-flex w-fit items-center justify-center px-1.5 py-0.5 rounded-full text-[10px] font-medium shadow-[0px_6px_6px_-3px_rgba(0,0,0,0.08),0px_3px_3px_-1.5px_rgba(0,0,0,0.08),0px_1px_1px_-0.5px_rgba(0,0,0,0.08),0px_0px_0px_1px_rgba(255,255,255,0.12)_inset,0px_1px_0px_0px_rgba(255,255,255,0.12)_inset]">
              Popular
            </span>
          )}
          {/* Show upgrade badge for yearly plans when user is on monthly */}
          {!tier.isPopular && isAuthenticated && currentSubscription && billingPeriod === 'yearly' && 
            currentTier && currentSubscription.price_id === currentTier.stripePriceId && 
            tier.yearlyStripePriceId && (currentTier.name === tier.name || 
            parseFloat(tier.price.slice(1)) >= parseFloat(currentTier.price.slice(1))) && (
            <span className="bg-green-500/10 text-green-700 text-[10px] font-medium px-1.5 py-0.5 rounded-full">
              Recommended
            </span>
          )}
          {isAuthenticated && statusBadge}
        </p>
        <div className="flex items-baseline mt-2">
          {billingPeriod === 'yearly' && tier.yearlyPrice && displayPrice !== '$0' ? (
            <div className="flex flex-col">
              <div className="flex items-baseline gap-2">
                <PriceDisplay price={`$${Math.round(parseFloat(tier.yearlyPrice.slice(1)) / 12)}`} isCompact={insideDialog} />
                {tier.discountPercentage && (
                  <span className="text-xs line-through text-muted-foreground">
                    ${Math.round(parseFloat(tier.originalYearlyPrice?.slice(1) || '0') / 12)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-muted-foreground">/month</span>
                <span className="text-xs text-muted-foreground">billed yearly</span>
              </div>
            </div>
          ) : (
            <div className="flex items-baseline">
              <PriceDisplay price={displayPrice} isCompact={insideDialog} />
              <span className="ml-2">{displayPrice !== '$0' ? '/month' : ''}</span>
            </div>
          )}
        </div>
        <p className="text-sm mt-2">{tier.description}</p>

        {billingPeriod === 'yearly' && tier.yearlyPrice && tier.discountPercentage ? (
          <div className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-green-50 border-green-200 text-green-700 w-fit">
            Save ${Math.round(parseFloat(tier.originalYearlyPrice?.slice(1) || '0') - parseFloat(tier.yearlyPrice.slice(1)))} per year
          </div>
        ) : (
          <div className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-primary/10 border-primary/20 text-primary w-fit">
            {billingPeriod === 'yearly' && tier.yearlyPrice && displayPrice !== '$0' 
              ? `$${Math.round(parseFloat(tier.yearlyPrice.slice(1)) / 12)}/month (billed yearly)`
              : `${displayPrice}/month`
            }
          </div>
        )}
      </div>

      <div className={cn(
        "flex-grow",
        insideDialog ? "px-3 pb-2" : "px-4 pb-3"
      )}>
        {tier.features && tier.features.length > 0 && (
          <ul className="space-y-3">
            {tier.features.map((feature) => (
              <li key={feature} className="flex items-center gap-2">
                <div className="size-5 min-w-5 rounded-full border border-primary/20 flex items-center justify-center">
                  <CheckIcon className="size-3 text-primary" />
                </div>
                <span className="text-sm">{feature}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={cn(
        "mt-auto",
        insideDialog ? "px-3 pt-1 pb-3" : "px-4 pt-2 pb-4"
      )}>
        <Button
          onClick={() => handleSubscribe(tierPriceId)}
          disabled={buttonDisabled}
          variant={buttonVariant || 'default'}
          className={cn(
            'w-full font-medium transition-all duration-200',
            isCompact || insideDialog ? 'h-8 rounded-md text-xs' : 'h-10 rounded-full text-sm',
            buttonClassName,
            isPlanLoading && 'animate-pulse',
          )}
        >
          {buttonText}
        </Button>
      </div>
    </div>
  );
}

interface PricingSectionProps {
  returnUrl?: string;
  showTitleAndTabs?: boolean;
  hideFree?: boolean;
  insideDialog?: boolean;
}

export function PricingSection({
  returnUrl = typeof window !== 'undefined' ? window.location.href : '/',
  showTitleAndTabs = true,
  hideFree = false,
  insideDialog = false
}: PricingSectionProps) {
  const [deploymentType, setDeploymentType] = useState<'cloud' | 'self-hosted'>(
    'cloud',
  );
  const { data: subscriptionData, isLoading: isFetchingPlan, error: subscriptionQueryError, refetch: refetchSubscription } = useSubscription();

  // Derive authentication and subscription status from the hook data
  const isAuthenticated = !!subscriptionData && subscriptionQueryError === null;
  const currentSubscription = subscriptionData || null;

  // Determine default billing period based on user's current subscription
  const getDefaultBillingPeriod = (): 'monthly' | 'yearly' => {
    if (!isAuthenticated || !currentSubscription) {
      // Default to yearly for non-authenticated users or users without subscription
      return 'yearly';
    }

    // Find current tier to determine if user is on monthly or yearly plan
    const currentTier = siteConfig.cloudPricingItems.find(
      (p) => p.stripePriceId === currentSubscription.price_id || p.yearlyStripePriceId === currentSubscription.price_id,
    );

    if (currentTier) {
      // Check if current subscription is yearly
      if (currentTier.yearlyStripePriceId === currentSubscription.price_id) {
        return 'yearly';
      } else if (currentTier.stripePriceId === currentSubscription.price_id) {
        return 'monthly';
      }
    }

    // Default to yearly if we can't determine current plan type
    return 'yearly';
  };

  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>(getDefaultBillingPeriod());
  const [planLoadingStates, setPlanLoadingStates] = useState<Record<string, boolean>>({});

  // Update billing period when subscription data changes
  useEffect(() => {
    setBillingPeriod(getDefaultBillingPeriod());
  }, [isAuthenticated, currentSubscription?.price_id]);

  const handlePlanSelect = (planId: string) => {
    setPlanLoadingStates((prev) => ({ ...prev, [planId]: true }));
  };

  const handleSubscriptionUpdate = () => {
    refetchSubscription();
    // The useSubscription hook will automatically refetch, so we just need to clear loading states
    setTimeout(() => {
      setPlanLoadingStates({});
    }, 1000);
  };

  const handleTabChange = (tab: 'cloud' | 'self-hosted') => {
    if (tab === 'self-hosted') {
      const openSourceSection = document.getElementById('open-source');
      if (openSourceSection) {
        const rect = openSourceSection.getBoundingClientRect();
        const scrollTop =
          window.pageYOffset || document.documentElement.scrollTop;
        const offsetPosition = scrollTop + rect.top - 100;

        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth',
        });
      }
    } else {
      setDeploymentType(tab);
    }
  };

  if (isLocalMode()) {
    return (
      <div className="p-4 bg-muted/30 border border-border rounded-lg text-center">
        <p className="text-sm text-muted-foreground">
          Running in local development mode - billing features are disabled
        </p>
      </div>
    );
  }

  return (
    <section
      id="pricing"
      className={cn("flex flex-col items-center justify-center gap-10 w-full relative")}
    >
      {showTitleAndTabs && (
        <>
          <SectionHeader>
            <h2 className="text-3xl md:text-4xl font-medium tracking-tighter text-center text-balance">
              Choose the right plan for your needs
            </h2>
            <p className="text-muted-foreground text-center text-balance font-medium">
              Start with our free plan or upgrade to a premium plan for more
              usage hours
            </p>
          </SectionHeader>
          <div className="relative w-full h-full">
            <div className="absolute -top-14 left-1/2 -translate-x-1/2">
              <PricingTabs
                activeTab={deploymentType}
                setActiveTab={handleTabChange}
                className="mx-auto"
              />
            </div>
          </div>
        </>
      )}

      {deploymentType === 'cloud' && (
        <BillingPeriodToggle 
          billingPeriod={billingPeriod} 
          setBillingPeriod={setBillingPeriod} 
        />
      )}

      {deploymentType === 'cloud' && (
        <div className={cn(
          "grid gap-4 w-full mx-auto",
          {
            "px-6 max-w-7xl": !insideDialog,
            "max-w-7xl": insideDialog
          },
          insideDialog 
            ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 2xl:grid-cols-4"
            : "min-[650px]:grid-cols-2 lg:grid-cols-4",
          !insideDialog && "grid-rows-1 items-stretch"
        )}>
          {siteConfig.cloudPricingItems
            .filter((tier) => !tier.hidden && (!hideFree || tier.price !== '$0'))
            .map((tier) => (
            <PricingTier
              key={tier.name}
              tier={tier}
              currentSubscription={currentSubscription}
              isLoading={planLoadingStates}
              isFetchingPlan={isFetchingPlan}
              onPlanSelect={handlePlanSelect}
              onSubscriptionUpdate={handleSubscriptionUpdate}
              isAuthenticated={isAuthenticated}
              returnUrl={returnUrl}
              insideDialog={insideDialog}
              billingPeriod={billingPeriod}
            />
          ))}
        </div>
      )}
    </section>
  );
}
