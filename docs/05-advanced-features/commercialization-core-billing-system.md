# 商业化核心：计费系统

## 概述

本文档详细阐述了 Suna 项目的商业化核心系统设计，涵盖 Stripe 订阅管理集成、Token 使用量追踪、成本核算、多层级订阅计划以及模型访问权限控制等关键功能模块。该系统旨在为 AI 应用提供完整的商业化解决方案，实现精准计费、灵活定价和权限管理。

## 系统架构

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                      前端应用层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ 订阅管理 │ │ 账单查看 │ │ 用量统计 │ │ 套餐选择 │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      API 网关层                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ 身份验证     │ │ 权限校验     │ │ 限流控制     │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    业务逻辑层                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ 订阅服务     │ │ 计费服务     │ │ 权限服务     │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据存储层                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ 用户数据     │ │ 使用记录     │ │ 交易记录     │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    外部服务集成                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ Stripe API   │ │ OpenAI API   │ │ 监控服务     │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 1. Stripe 订阅管理集成

### 1.1 集成概述

Stripe 作为全球领先的支付处理平台，为我们提供了完整的订阅管理解决方案。通过深度集成 Stripe API，我们能够实现：

- 自动化的订阅生命周期管理
- 灵活的计费周期（月度/年度）
- 多种支付方式支持
- 自动续费和失败重试机制
- 发票自动生成和邮件通知

### 1.2 技术实现

#### 1.2.1 Webhook 事件处理

```typescript
// webhook 事件类型定义
interface StripeWebhookEvent {
  id: string;
  type: string;
  data: {
    object: any;
  };
  created: number;
}

// 核心事件处理器
class StripeWebhookHandler {
  // 订阅创建事件
  async handleSubscriptionCreated(subscription: Stripe.Subscription) {
    // 1. 更新用户订阅状态
    // 2. 分配相应权限
    // 3. 发送欢迎邮件
    // 4. 记录审计日志
  }

  // 订阅更新事件
  async handleSubscriptionUpdated(subscription: Stripe.Subscription) {
    // 1. 同步订阅状态
    // 2. 调整用户权限
    // 3. 处理升降级逻辑
  }

  // 支付成功事件
  async handlePaymentSucceeded(invoice: Stripe.Invoice) {
    // 1. 更新支付记录
    // 2. 重置用量限额
    // 3. 发送支付确认
  }

  // 支付失败事件
  async handlePaymentFailed(invoice: Stripe.Invoice) {
    // 1. 发送催款通知
    // 2. 设置宽限期
    // 3. 限制服务访问
  }
}
```

#### 1.2.2 订阅管理 API

```typescript
class SubscriptionService {
  // 创建新订阅
  async createSubscription(userId: string, planId: string, paymentMethodId: string) {
    // 1. 验证用户身份
    // 2. 检查现有订阅
    // 3. 创建或更新 Stripe Customer
    // 4. 创建订阅
    // 5. 同步本地数据
  }

  // 更改订阅计划
  async updateSubscription(userId: string, newPlanId: string) {
    // 1. 获取当前订阅
    // 2. 计算按比例收费
    // 3. 执行计划变更
    // 4. 更新权限配置
  }

  // 取消订阅
  async cancelSubscription(userId: string, immediately: boolean = false) {
    // 1. 设置取消策略
    // 2. 处理退款逻辑
    // 3. 保留历史数据
    // 4. 降级到免费计划
  }

  // 恢复订阅
  async resumeSubscription(userId: string) {
    // 1. 检查订阅状态
    // 2. 更新支付方式
    // 3. 重新激活订阅
  }
}
```

### 1.3 安全性考虑

- **Webhook 签名验证**：确保所有来自 Stripe 的请求都经过签名验证
- **幂等性处理**：防止重复处理同一事件
- **敏感数据加密**：所有支付相关信息在存储时进行加密
- **PCI 合规性**：不存储信用卡信息，完全依赖 Stripe 的安全基础设施

## 2. Token 使用量追踪和成本核算

### 2.1 追踪机制

Token 使用量追踪是精准计费的基础，我们实现了多维度的追踪系统：

#### 2.1.1 实时追踪

```typescript
interface TokenUsage {
  userId: string;
  modelId: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  requestId: string;
  timestamp: Date;
  metadata: {
    endpoint: string;
    responseTime: number;
    statusCode: number;
  };
}

class TokenTracker {
  // 记录单次请求的 Token 使用
  async trackUsage(usage: TokenUsage) {
    // 1. 写入时序数据库（用于实时监控）
    await this.writeToTimeSeries(usage);
    
    // 2. 更新用户累计使用量（Redis）
    await this.updateUserQuota(usage.userId, usage.totalTokens);
    
    // 3. 检查是否超出限额
    await this.checkQuotaLimit(usage.userId);
    
    // 4. 异步写入持久化存储
    await this.persistUsageRecord(usage);
  }

  // 聚合统计
  async aggregateUsage(userId: string, period: DateRange) {
    // 1. 按模型聚合
    // 2. 按时间聚合
    // 3. 计算成本
    // 4. 生成报表
  }
}
```

#### 2.1.2 批量处理优化

```typescript
class BatchProcessor {
  private queue: TokenUsage[] = [];
  private batchSize = 1000;
  private flushInterval = 5000; // 5秒

  async addToQueue(usage: TokenUsage) {
    this.queue.push(usage);
    
    if (this.queue.length >= this.batchSize) {
      await this.flush();
    }
  }

  async flush() {
    if (this.queue.length === 0) return;
    
    const batch = this.queue.splice(0, this.batchSize);
    await this.processBatch(batch);
  }

  private async processBatch(batch: TokenUsage[]) {
    // 1. 批量写入数据库
    // 2. 批量更新缓存
    // 3. 触发计费计算
  }
}
```

### 2.2 成本核算模型

#### 2.2.1 动态定价策略

```typescript
interface PricingModel {
  modelId: string;
  baseCost: {
    prompt: number;    // 每1K tokens 的成本
    completion: number; // 每1K tokens 的成本
  };
  markupRatio: number; // 加价比例
  volumeDiscounts: Array<{
    threshold: number;
    discount: number;
  }>;
}

class CostCalculator {
  // 计算单次请求成本
  calculateRequestCost(usage: TokenUsage, pricing: PricingModel): number {
    const promptCost = (usage.promptTokens / 1000) * pricing.baseCost.prompt;
    const completionCost = (usage.completionTokens / 1000) * pricing.baseCost.completion;
    const baseCost = promptCost + completionCost;
    
    // 应用加价
    const markedUpCost = baseCost * (1 + pricing.markupRatio);
    
    // 应用批量折扣
    const discount = this.getVolumeDiscount(usage.userId, pricing);
    return markedUpCost * (1 - discount);
  }

  // 月度账单计算
  async calculateMonthlyBill(userId: string, month: Date) {
    // 1. 获取该月所有使用记录
    // 2. 按模型分组计算
    // 3. 应用套餐优惠
    // 4. 计算税费
    // 5. 生成详细账单
  }
}
```

#### 2.2.2 成本优化建议

```typescript
class CostOptimizer {
  // 分析使用模式
  async analyzeUsagePattern(userId: string) {
    return {
      // 高频使用场景
      hotspots: this.identifyHotspots(userId),
      // 低效请求识别
      inefficientRequests: this.findInefficientRequests(userId),
      // 模型选择建议
      modelRecommendations: this.recommendModels(userId),
      // 预估节省金额
      potentialSavings: this.calculateSavings(userId)
    };
  }

  // 自动优化策略
  async applyOptimizations(userId: string, strategies: string[]) {
    // 1. 请求合并
    // 2. 缓存复用
    // 3. 模型降级
    // 4. 批处理优化
  }
}
```

## 3. 多层级订阅计划

### 3.1 订阅层级设计

```typescript
enum PlanTier {
  FREE = 'free',
  STARTER = 'starter',
  PROFESSIONAL = 'professional',
  ENTERPRISE = 'enterprise'
}

interface SubscriptionPlan {
  id: string;
  tier: PlanTier;
  name: string;
  monthlyPrice: number;
  yearlyPrice: number;
  features: PlanFeatures;
  limits: PlanLimits;
}

interface PlanFeatures {
  // 基础功能
  apiAccess: boolean;
  webhookSupport: boolean;
  customDomain: boolean;
  
  // 高级功能
  prioritySupport: boolean;
  slaGuarantee: boolean;
  customModels: boolean;
  whiteLabeling: boolean;
  
  // 企业功能
  sso: boolean;
  auditLogs: boolean;
  roleBasedAccess: boolean;
  dedicatedInfra: boolean;
}

interface PlanLimits {
  // Token 限制
  monthlyTokens: number;
  burstTokens: number;
  
  // 请求限制
  requestsPerMinute: number;
  requestsPerDay: number;
  
  // 并发限制
  concurrentRequests: number;
  
  // 存储限制
  dataRetentionDays: number;
  maxFileSize: number;
  
  // 团队限制
  teamMembers: number;
  apiKeys: number;
}
```

### 3.2 计划配置示例

```typescript
const subscriptionPlans: SubscriptionPlan[] = [
  {
    id: 'free',
    tier: PlanTier.FREE,
    name: '免费版',
    monthlyPrice: 0,
    yearlyPrice: 0,
    features: {
      apiAccess: true,
      webhookSupport: false,
      customDomain: false,
      prioritySupport: false,
      slaGuarantee: false,
      customModels: false,
      whiteLabeling: false,
      sso: false,
      auditLogs: false,
      roleBasedAccess: false,
      dedicatedInfra: false
    },
    limits: {
      monthlyTokens: 100_000,
      burstTokens: 10_000,
      requestsPerMinute: 3,
      requestsPerDay: 100,
      concurrentRequests: 1,
      dataRetentionDays: 7,
      maxFileSize: 5 * 1024 * 1024, // 5MB
      teamMembers: 1,
      apiKeys: 1
    }
  },
  {
    id: 'starter',
    tier: PlanTier.STARTER,
    name: '入门版',
    monthlyPrice: 49,
    yearlyPrice: 490,
    features: {
      apiAccess: true,
      webhookSupport: true,
      customDomain: false,
      prioritySupport: false,
      slaGuarantee: false,
      customModels: false,
      whiteLabeling: false,
      sso: false,
      auditLogs: true,
      roleBasedAccess: false,
      dedicatedInfra: false
    },
    limits: {
      monthlyTokens: 2_000_000,
      burstTokens: 200_000,
      requestsPerMinute: 20,
      requestsPerDay: 5_000,
      concurrentRequests: 5,
      dataRetentionDays: 30,
      maxFileSize: 50 * 1024 * 1024, // 50MB
      teamMembers: 5,
      apiKeys: 10
    }
  },
  {
    id: 'professional',
    tier: PlanTier.PROFESSIONAL,
    name: '专业版',
    monthlyPrice: 299,
    yearlyPrice: 2_990,
    features: {
      apiAccess: true,
      webhookSupport: true,
      customDomain: true,
      prioritySupport: true,
      slaGuarantee: true,
      customModels: true,
      whiteLabeling: false,
      sso: true,
      auditLogs: true,
      roleBasedAccess: true,
      dedicatedInfra: false
    },
    limits: {
      monthlyTokens: 20_000_000,
      burstTokens: 2_000_000,
      requestsPerMinute: 100,
      requestsPerDay: 50_000,
      concurrentRequests: 20,
      dataRetentionDays: 90,
      maxFileSize: 500 * 1024 * 1024, // 500MB
      teamMembers: 50,
      apiKeys: 100
    }
  },
  {
    id: 'enterprise',
    tier: PlanTier.ENTERPRISE,
    name: '企业版',
    monthlyPrice: -1, // 定制价格
    yearlyPrice: -1,
    features: {
      apiAccess: true,
      webhookSupport: true,
      customDomain: true,
      prioritySupport: true,
      slaGuarantee: true,
      customModels: true,
      whiteLabeling: true,
      sso: true,
      auditLogs: true,
      roleBasedAccess: true,
      dedicatedInfra: true
    },
    limits: {
      monthlyTokens: -1, // 无限制
      burstTokens: -1,
      requestsPerMinute: -1,
      requestsPerDay: -1,
      concurrentRequests: -1,
      dataRetentionDays: 365,
      maxFileSize: -1,
      teamMembers: -1,
      apiKeys: -1
    }
  }
];
```

### 3.3 升降级处理

```typescript
class PlanMigrationService {
  // 计划升级
  async upgradePlan(userId: string, fromPlan: PlanTier, toPlan: PlanTier) {
    // 1. 验证升级路径有效性
    if (!this.isValidUpgrade(fromPlan, toPlan)) {
      throw new Error('Invalid upgrade path');
    }
    
    // 2. 计算按比例收费
    const proratedAmount = await this.calculateProration(userId, fromPlan, toPlan);
    
    // 3. 立即生效新权限
    await this.applyNewPermissions(userId, toPlan);
    
    // 4. 迁移数据和配置
    await this.migrateUserData(userId, fromPlan, toPlan);
    
    // 5. 发送升级确认
    await this.sendUpgradeNotification(userId, toPlan);
  }

  // 计划降级
  async downgradePlan(userId: string, fromPlan: PlanTier, toPlan: PlanTier) {
    // 1. 检查降级影响
    const impact = await this.assessDowngradeImpact(userId, fromPlan, toPlan);
    
    // 2. 如果有数据超限，提供迁移选项
    if (impact.hasOverage) {
      await this.handleOverageData(userId, impact);
    }
    
    // 3. 设置降级生效时间（通常在计费周期结束）
    await this.scheduleDowngrade(userId, toPlan);
    
    // 4. 发送降级通知和影响说明
    await this.sendDowngradeNotification(userId, toPlan, impact);
  }

  // 特殊处理：试用期转换
  async convertFromTrial(userId: string, selectedPlan: PlanTier) {
    // 1. 验证试用期状态
    // 2. 保留试用期间的使用数据
    // 3. 无缝转换到付费计划
    // 4. 应用首次付费优惠
  }
}
```

## 4. 模型访问权限控制

### 4.1 权限模型设计

```typescript
interface ModelAccessControl {
  modelId: string;
  requiredTier: PlanTier[];
  quotaMultiplier: number; // Token 消耗倍数
  rateLimit: {
    requestsPerMinute: number;
    tokensPerMinute: number;
  };
  features: {
    streaming: boolean;
    functionCalling: boolean;
    visionCapability: boolean;
    maxContextLength: number;
  };
}

// 模型权限配置
const modelAccessMatrix: ModelAccessControl[] = [
  {
    modelId: 'gpt-3.5-turbo',
    requiredTier: [PlanTier.FREE, PlanTier.STARTER, PlanTier.PROFESSIONAL, PlanTier.ENTERPRISE],
    quotaMultiplier: 1,
    rateLimit: {
      requestsPerMinute: 60,
      tokensPerMinute: 90_000
    },
    features: {
      streaming: true,
      functionCalling: true,
      visionCapability: false,
      maxContextLength: 4_096
    }
  },
  {
    modelId: 'gpt-4',
    requiredTier: [PlanTier.STARTER, PlanTier.PROFESSIONAL, PlanTier.ENTERPRISE],
    quotaMultiplier: 20,
    rateLimit: {
      requestsPerMinute: 20,
      tokensPerMinute: 40_000
    },
    features: {
      streaming: true,
      functionCalling: true,
      visionCapability: false,
      maxContextLength: 8_192
    }
  },
  {
    modelId: 'gpt-4-turbo',
    requiredTier: [PlanTier.PROFESSIONAL, PlanTier.ENTERPRISE],
    quotaMultiplier: 10,
    rateLimit: {
      requestsPerMinute: 30,
      tokensPerMinute: 60_000
    },
    features: {
      streaming: true,
      functionCalling: true,
      visionCapability: true,
      maxContextLength: 128_000
    }
  },
  {
    modelId: 'claude-3-opus',
    requiredTier: [PlanTier.ENTERPRISE],
    quotaMultiplier: 30,
    rateLimit: {
      requestsPerMinute: 10,
      tokensPerMinute: 30_000
    },
    features: {
      streaming: true,
      functionCalling: false,
      visionCapability: true,
      maxContextLength: 200_000
    }
  }
];
```

### 4.2 权限验证中间件

```typescript
class ModelAccessMiddleware {
  // 请求拦截和权限验证
  async validateAccess(request: ModelRequest): Promise<ValidationResult> {
    const user = await this.getUserWithPlan(request.userId);
    const modelConfig = this.getModelConfig(request.modelId);
    
    // 1. 检查计划权限
    if (!modelConfig.requiredTier.includes(user.planTier)) {
      return {
        allowed: false,
        reason: 'Model not available in current plan',
        suggestedUpgrade: this.getSuggestedPlan(request.modelId)
      };
    }
    
    // 2. 检查配额
    const quotaCheck = await this.checkQuota(user, modelConfig);
    if (!quotaCheck.hasQuota) {
      return {
        allowed: false,
        reason: 'Quota exceeded',
        quotaReset: quotaCheck.resetTime
      };
    }
    
    // 3. 检查速率限制
    const rateLimitCheck = await this.checkRateLimit(user, modelConfig);
    if (!rateLimitCheck.allowed) {
      return {
        allowed: false,
        reason: 'Rate limit exceeded',
        retryAfter: rateLimitCheck.retryAfter
      };
    }
    
    // 4. 检查功能权限
    const featureCheck = this.validateFeatures(request, modelConfig);
    if (!featureCheck.allowed) {
      return {
        allowed: false,
        reason: featureCheck.reason
      };
    }
    
    return { allowed: true };
  }

  // 动态权限调整
  async adjustPermissions(userId: string, adjustments: PermissionAdjustment) {
    // 1. 临时提权（如试用高级模型）
    // 2. 特殊活动权限
    // 3. 企业定制权限
  }
}
```

### 4.3 权限审计和监控

```typescript
class AccessAuditService {
  // 记录所有访问尝试
  async logAccessAttempt(attempt: AccessAttempt) {
    const auditRecord = {
      timestamp: new Date(),
      userId: attempt.userId,
      modelId: attempt.modelId,
      allowed: attempt.result.allowed,
      reason: attempt.result.reason,
      requestMetadata: {
        ip: attempt.ip,
        userAgent: attempt.userAgent,
        apiKeyId: attempt.apiKeyId
      }
    };
    
    // 1. 实时写入审计日志
    await this.writeAuditLog(auditRecord);
    
    // 2. 异常行为检测
    if (this.isAnomalous(attempt)) {
      await this.alertSecurityTeam(attempt);
    }
    
    // 3. 合规性报告生成
    await this.updateComplianceMetrics(auditRecord);
  }

  // 生成访问报告
  async generateAccessReport(userId: string, period: DateRange) {
    return {
      summary: {
        totalRequests: 0,
        allowedRequests: 0,
        deniedRequests: 0,
        uniqueModels: [],
        totalTokensUsed: 0
      },
      denialReasons: {
        quotaExceeded: 0,
        rateLimited: 0,
        insufficientPlan: 0,
        featureRestricted: 0
      },
      recommendations: []
    };
  }
}
```

## 5. 系统集成和最佳实践

### 5.1 微服务架构

```yaml
# docker-compose.yml 示例
version: '3.8'
services:
  billing-service:
    image: suna/billing-service
    environment:
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - postgres
      - redis
      
  usage-tracker:
    image: suna/usage-tracker
    environment:
      - TIMESCALE_URL=${TIMESCALE_URL}
      - KAFKA_BROKERS=${KAFKA_BROKERS}
    depends_on:
      - timescaledb
      - kafka
      
  permission-service:
    image: suna/permission-service
    environment:
      - CACHE_URL=${REDIS_URL}
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - postgres
      - redis
```

### 5.2 监控和告警

```typescript
// 关键指标监控
interface BillingMetrics {
  // 业务指标
  mrr: number; // 月度经常性收入
  arr: number; // 年度经常性收入
  churnRate: number; // 流失率
  ltv: number; // 客户生命周期价值
  
  // 技术指标
  paymentSuccessRate: number;
  webhookProcessingTime: number;
  quotaUtilization: number;
  apiErrorRate: number;
  
  // 用户体验指标
  upgradeFunnel: {
    visited: number;
    started: number;
    completed: number;
  };
  supportTickets: {
    billingRelated: number;
    averageResolutionTime: number;
  };
}

// 告警规则
const alertRules = [
  {
    metric: 'paymentSuccessRate',
    threshold: 0.95,
    operator: '<',
    severity: 'critical'
  },
  {
    metric: 'webhookProcessingTime',
    threshold: 5000, // 5秒
    operator: '>',
    severity: 'warning'
  },
  {
    metric: 'churnRate',
    threshold: 0.05, // 5%
    operator: '>',
    severity: 'warning'
  }
];
```

### 5.3 灾难恢复

```typescript
class DisasterRecovery {
  // 数据备份策略
  async backupBillingData() {
    // 1. 每日全量备份
    // 2. 每小时增量备份
    // 3. 跨区域复制
    // 4. 加密存储
  }
  
  // 故障转移
  async failover() {
    // 1. 切换到备用支付网关
    // 2. 启用降级模式
    // 3. 通知受影响用户
    // 4. 记录故障时间用于 SLA 补偿
  }
  
  // 数据一致性检查
  async reconciliation() {
    // 1. 对账 Stripe 交易
    // 2. 验证本地记录
    // 3. 修复不一致数据
    // 4. 生成对账报告
  }
}
```

## 6. 合规性和安全性

### 6.1 数据保护

- **PCI DSS 合规**：不存储敏感支付信息
- **GDPR 合规**：用户数据删除和导出功能
- **SOC 2 认证**：安全控制和审计跟踪
- **加密标准**：AES-256 加密存储，TLS 1.3 传输

### 6.2 安全措施

```typescript
// 安全配置示例
const securityConfig = {
  // API 密钥轮换
  apiKeyRotation: {
    enabled: true,
    intervalDays: 90,
    graceperiodDays: 7
  },
  
  // 异常检测
  anomalyDetection: {
    enabled: true,
    rules: [
      { type: 'usage_spike', threshold: 10 },
      { type: 'location_change', sensitivity: 'high' },
      { type: 'concurrent_usage', maxSessions: 5 }
    ]
  },
  
  // 访问控制
  accessControl: {
    mfa: 'required_for_billing',
    ipWhitelist: true,
    sessionTimeout: 3600
  }
};
```

## 7. 总结

本计费系统通过整合 Stripe 订阅管理、精准的 Token 使用追踪、灵活的多层级订阅计划和细粒度的模型访问控制，为 AI 应用提供了完整的商业化解决方案。系统设计充分考虑了可扩展性、可靠性和安全性，能够支撑从初创项目到大规模企业应用的各种场景。

关键成功因素：
1. **透明的计费模式**：用户清楚了解费用构成
2. **灵活的订阅选项**：满足不同规模客户需求
3. **精准的使用追踪**：确保计费准确性
4. **强大的权限控制**：保护高价值资源
5. **卓越的用户体验**：简化升级和支付流程
6. **可靠的基础设施**：确保 99.99% 可用性

通过持续优化和迭代，该系统将成为 Suna 项目商业成功的坚实基础。