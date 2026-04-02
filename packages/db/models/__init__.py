from packages.db.models.core import Organization, User, Brand, Avatar, AvatarProviderProfile, VoiceProviderProfile
from packages.db.models.accounts import CreatorAccount, AccountPortfolio
from packages.db.models.offers import Offer, SponsorProfile, SponsorOpportunity, LtvModel, AudienceSegment
from packages.db.models.discovery import TopicSource, TopicCandidate, NicheCluster, TrendSignal, TopicSignal
from packages.db.models.scoring import OpportunityScore, ProfitForecast, OfferFitScore, RecommendationQueue, SaturationReport
from packages.db.models.content import ContentBrief, Script, ScriptVariant, Asset, MediaJob, ContentItem
from packages.db.models.quality import QAReport, SimilarityReport, Approval
from packages.db.models.publishing import PublishJob, PerformanceMetric, AttributionEvent, SignalIngestionRun
from packages.db.models.experiments import Experiment, ExperimentVariant, WinnerCloneJob
from packages.db.models.learning import MemoryEntry, CommentIngestion, CommentCluster, CommentCashSignal, KnowledgeGraphNode, KnowledgeGraphEdge
from packages.db.models.portfolio import (
    PortfolioAllocation, ScaleRecommendation, CapitalAllocationRecommendation,
    RevenuLeakReport, GeoLanguageExpansionRecommendation, PaidAmplificationJob, TrustSignalReport,
    RoadmapRecommendation, MonetizationRecommendation,
)
from packages.db.models.decisions import (
    OpportunityDecision, MonetizationDecision, PublishDecision,
    SuppressionDecision, ScaleDecision, AllocationDecision, ExpansionDecision,
)
from packages.db.models.scale_alerts import (
    OperatorAlert, LaunchCandidate, ScaleBlockerReport,
    NotificationDelivery, LaunchReadinessReport, GrowthCommand, GrowthCommandRun,
)
from packages.db.models.system import SuppressionAction, AuditLog, SystemJob, ProviderUsageCost
from packages.db.models.growth_pack import (
    PortfolioLaunchPlan, AccountLaunchBlueprint, PlatformAllocationReport,
    NicheDeploymentReport, GrowthPackBlockerReport, CapitalDeploymentPlan,
    CrossAccountCannibalizationReport, PortfolioOutputReport,
)
from packages.db.models.revenue_ceiling_phase_a import (
    OfferLadder, OwnedAudienceAsset, OwnedAudienceEvent,
    MessageSequence, MessageSequenceStep, FunnelStageMetric, FunnelLeakFix,
)
from packages.db.models.revenue_ceiling_phase_b import (
    HighTicketOpportunity,
    ProductOpportunity,
    RevenueDensityReport,
    UpsellRecommendation,
)
from packages.db.models.revenue_ceiling_phase_c import (
    RecurringRevenueModel,
    SponsorInventory,
    SponsorPackageRecommendation,
    TrustConversionReport,
    MonetizationMixReport,
    PaidPromotionCandidate,
)
from packages.db.models.expansion_pack2_phase_a import (
    LeadOpportunity,
    CloserAction,
    LeadQualificationReport,
    OwnedOfferRecommendation,
)
from packages.db.models.expansion_pack2_phase_b import (
    PricingRecommendation,
    BundleRecommendation,
    RetentionRecommendation,
    ReactivationCampaign,
)
from packages.db.models.expansion_pack2_phase_c import (
    ReferralProgramRecommendation,
    CompetitiveGapReport,
    SponsorTarget,
    SponsorOutreachSequence,
    ProfitGuardrailReport,
)
from packages.db.models.experiment_decisions import (
    ExperimentDecision,
    ExperimentOutcome,
    ExperimentOutcomeAction,
)
from packages.db.models.contribution import (
    ContributionReport,
    AttributionModelRun,
)
from packages.db.models.capacity import (
    CapacityReport,
    QueueAllocationDecision,
)
from packages.db.models.offer_lifecycle import (
    OfferLifecycleReport,
    OfferLifecycleEvent,
)
from packages.db.models.creative_memory import (
    CreativeMemoryAtom,
    CreativeMemoryLink,
)
from packages.db.models.recovery import (
    RecoveryIncident,
    RecoveryAction,
)
from packages.db.models.deal_desk import (
    DealDeskRecommendation,
    DealDeskEvent,
)
from packages.db.models.kill_ledger import (
    KillLedgerEntry,
    KillHindsightReview,
)
from packages.db.models.audience_state import (
    AudienceStateReport,
    AudienceStateEvent,
)
from packages.db.models.reputation import (
    ReputationReport,
    ReputationEvent,
)
from packages.db.models.market_timing import (
    MarketTimingReport,
    MacroSignalEvent,
)
from packages.db.models.autonomous_execution import (
    AutomationExecutionPolicy,
    AutomationExecutionRun,
    ExecutionBlockerEscalation,
)
from packages.db.models.autonomous_phase_a import (
    SignalScanRun,
    NormalizedSignalEvent,
    AutoQueueItem,
    AccountWarmupPlan,
    AccountOutputReport,
    AccountMaturityReport,
    PlatformWarmupPolicy,
    OutputRampEvent,
)
from packages.db.models.autonomous_phase_b import (
    ExecutionPolicy,
    AutonomousRun,
    AutonomousRunStep,
    DistributionPlan,
    MonetizationRoute,
    SuppressionExecution,
    ExecutionFailure,
)
from packages.db.models.autonomous_phase_c import (
    FunnelExecutionRun,
    PaidOperatorRun,
    PaidOperatorDecision,
    SponsorAutonomousAction,
    RetentionAutomationAction,
    RecoveryEscalation,
    SelfHealingAction,
)
from packages.db.models.autonomous_phase_d import (
    AgentRun,
    AgentMessage,
    RevenuePressureReport,
    OverridePolicy,
    EscalationEvent,
    BlockerDetectionReport,
    OperatorCommand,
)
from packages.db.models.brain_architecture import (
    BrainMemoryEntry,
    BrainMemoryLink,
    AccountStateSnapshot,
    OpportunityStateSnapshot,
    ExecutionStateSnapshot,
    AudienceStateSnapshotV2,
    StateTransitionEvent,
)
from packages.db.models.brain_phase_b import (
    BrainDecision,
    PolicyEvaluation,
    ConfidenceReport,
    UpsideCostEstimate,
    ArbitrationReport,
)
from packages.db.models.brain_phase_c import (
    AgentRegistryEntry,
    AgentRunV2,
    AgentMessageV2,
    WorkflowCoordinationRun,
    CoordinationDecision,
    SharedContextEvent,
)
from packages.db.models.brain_phase_d import (
    MetaMonitoringReport,
    SelfCorrectionAction,
    ReadinessBrainReport,
    BrainEscalation,
)
from packages.db.models.buffer_distribution import (
    BufferProfile,
    BufferPublishJob,
    BufferPublishAttempt,
    BufferStatusSync,
    BufferBlocker,
)
from packages.db.models.live_execution import (
    AnalyticsImport,
    AnalyticsEvent,
    ConversionImport,
    ConversionEvent,
    ExperimentObservationImport,
    ExperimentLiveResult,
    CrmContact,
    CrmSync,
    EmailSendRequest,
    SmsSendRequest,
    MessagingBlocker,
)
from packages.db.models.creator_revenue import (
    CreatorRevenueOpportunity,
    UgcServiceAction,
    ServiceConsultingAction,
    PremiumAccessAction,
    LicensingAction,
    SyndicationAction,
    DataProductAction,
    MerchAction,
    LiveEventAction,
    OwnedAffiliateProgramAction,
    AvenueExecutionTruth,
    CreatorRevenueBlocker,
    CreatorRevenueEvent,
)
from packages.db.models.live_execution_phase2 import (
    WebhookEvent, ExternalEventIngestion, SequenceTriggerAction,
    PaymentConnectorSync, PlatformAnalyticsSync, AdReportingImport,
    BufferExecutionTruth, BufferExecutionEvent, BufferRetryRecord, BufferCapabilityCheck,
)
from packages.db.models.provider_registry import (
    ProviderRegistryEntry, ProviderCapability, ProviderDependency,
    ProviderReadinessReport, ProviderUsageEvent, ProviderBlocker,
)
from packages.db.models.copilot import (
    CopilotChatSession, CopilotChatMessage, CopilotResponseCitation,
    CopilotActionSummary, CopilotIssueSummary,
)
from packages.db.models.gatekeeper import (
    GatekeeperCompletionReport,
    GatekeeperTruthReport,
    GatekeeperExecutionClosureReport,
    GatekeeperTestReport,
    GatekeeperDependencyReport,
    GatekeeperContradictionReport,
    GatekeeperOperatorCommandReport,
    GatekeeperExpansionPermission,
    GatekeeperAlert,
    GatekeeperAuditLedger,
)
from packages.db.models.expansion_advisor import AccountExpansionAdvisory
from packages.db.models.content_form import ContentFormRecommendation, ContentFormMixReport, ContentFormBlocker
from packages.db.models.content_routing import ContentRoutingDecision, ContentRoutingCostReport
from packages.db.models.pattern_memory import (
    WinningPatternMemory,
    WinningPatternEvidence,
    WinningPatternCluster,
    LosingPatternMemory,
    PatternReuseRecommendation,
    PatternDecayReport,
)
from packages.db.models.promote_winner import (
    ActiveExperiment,
    PWExperimentVariant,
    PWExperimentAssignment,
    PWExperimentObservation,
    PWExperimentWinner,
    PWExperimentLoser,
    PromotedWinnerRule,
)
from packages.db.models.capital_allocator import (
    CapitalAllocationReport,
    AllocationTarget,
    CAAllocationDecision,
    CAAllocationConstraint,
    CAAllocationRebalance,
)
from packages.db.models.account_state_intel import (
    AccountStateReport,
    AccountStateTransition,
    AccountStateAction,
)
from packages.db.models.quality_governor import (
    QualityGovernorReport,
    QualityDimensionScore,
    QualityBlock,
    QualityImprovementAction,
)
from packages.db.models.objection_mining import (
    ObjectionSignal,
    ObjectionCluster,
    ObjectionResponse,
    ObjectionPriorityReport,
)
from packages.db.models.opportunity_cost import (
    OpportunityCostReport,
    RankedAction,
    CostOfDelayModel,
)
from packages.db.models.failure_family import (
    FailureFamilyReport,
    FailureFamilyMember,
    SuppressionRule,
    SuppressionEvent,
)
from packages.db.models.trend_viral import (
    TrendSignalEvent, TrendVelocityReport, ViralOpportunity, TrendOpportunityScore,
    TrendDuplicate, TrendSuppressionRule, TrendBlocker, TrendSourceHealth,
)
from packages.db.models.autonomous_farm import (
    NicheScore, AccountWarmupPlan, FleetStatusReport, AccountVoiceProfile,
    ContentRepurposeRecord, CompetitorAccount, DailyIntelligenceReport,
)
from packages.db.models.ai_personality import (
    AIPersonality, PersonalityMemory, PersonalityEvolution,
)
from packages.db.models.cinema_studio import (
    StudioProject, StudioScene, CharacterBible, StylePreset,
    StudioGeneration, StudioActivity,
)
from packages.db.models.causal_attribution import (
    CausalAttributionReport, CausalSignal, CausalHypothesis, CausalConfidenceReport, CausalCreditAllocation,
)
from packages.db.models.operator_permission_matrix import (
    OperatorPermissionMatrix, AutonomyActionPolicy, ActionApprovalRequirement, ActionOverrideRule, ActionExecutionMode,
)
from packages.db.models.recovery_engine import (
    RecoveryIncidentV2, RollbackAction, RerouteAction, ThrottlingAction, RecoveryOutcome, RecoveryPlaybook,
)
from packages.db.models.digital_twin import (
    SimulationRun, SimulationScenario, SimulationAssumption, SimulationOutcome, SimulationRecommendation,
)
from packages.db.models.revenue_leak_detector import (
    RevenueLeakReport, RevenueLeakEvent, LeakCluster, LeakCorrectionAction, RevenueLossEstimate,
)
from packages.db.models.offer_lab import (
    OfferLabOffer, OfferLabVariant, OfferLabPricingTest, OfferLabPositioningTest,
    OfferLabBundle, OfferLabUpsell, OfferLabDownsell, OfferLabCrossSell,
    OfferLabBlocker, OfferLabLearning,
)
from packages.db.models.affiliate_enterprise import (
    AffiliateGovernanceRule, AffiliateBannedEntity, AffiliateApproval,
    AffiliateAuditEvent, AffiliateRiskFlag, OwnedAffiliatePartner, OwnedPartnerConversion,
)
from packages.db.models.executive_intel import (
    ExecutiveKPIReport, ExecutiveForecast, UsageCostReport, ProviderUptimeReport,
    OversightModeReport, ServiceHealthReport, ExecutiveAlert,
)
from packages.db.models.integrations_listening import (
    EnterpriseConnector, EnterpriseConnectorSync, SocialListeningEvent, CompetitorSignalEvent,
    InternalBusinessSignal, ListeningCluster, SignalResponseRecommendation, IntegrationBlocker,
)
from packages.db.models.hyperscale import (
    ExecutionCapacityReport, ExecutionQueueSegment, WorkloadAllocation, ThroughputEvent,
    BurstEvent, UsageCeilingRule, DegradationEvent, ScaleHealthReport,
)
from packages.db.models.workflow_builder import (
    WorkflowDefinition, WorkflowStep, WorkflowAssignment, WorkflowInstance,
    WorkflowInstanceStep, WorkflowApproval, WorkflowRejection, WorkflowOverride, WorkflowTemplate,
)
from packages.db.models.enterprise_security import (
    EnterpriseRole, EnterprisePermission, EnterpriseUserGroup, EnterpriseAccessScope,
    AuditTrailEvent, SensitiveDataPolicy, ModelIsolationPolicy,
    ComplianceControlReport, RiskOverrideEvent,
)
from packages.db.models.brand_governance import (
    BrandGovernanceProfile, BrandVoiceRule, BrandKnowledgeBase, BrandKnowledgeDocument,
    BrandAudienceProfile, BrandEditorialRule, BrandAssetLibrary, BrandStyleToken,
    BrandGovernanceViolation, BrandGovernanceApproval,
)
from packages.db.models.affiliate_intel import (
    AffiliateNetworkAccount, AffiliateMerchant, AffiliateOffer, AffiliateLink,
    AffiliateClickEvent, AffiliateConversionEvent, AffiliateCommissionEvent, AffiliatePayoutEvent,
    AffiliateBlocker, AffiliateDisclosure, AffiliateLeak,
)
from packages.db.models.landing_pages import LandingPage, LandingPageVariant, LandingPageBlock, LandingPageQualityReport, LandingPagePublishRecord
from packages.db.models.campaigns import Campaign, CampaignVariant, CampaignAsset, CampaignDestination, CampaignBlocker

__all__ = [
    "Organization", "User", "Brand", "Avatar", "AvatarProviderProfile", "VoiceProviderProfile",
    "CreatorAccount", "AccountPortfolio",
    "Offer", "SponsorProfile", "SponsorOpportunity", "LtvModel", "AudienceSegment",
    "TopicSource", "TopicCandidate", "NicheCluster", "TrendSignal", "TopicSignal",
    "OpportunityScore", "ProfitForecast", "OfferFitScore", "RecommendationQueue", "SaturationReport",
    "ContentBrief", "Script", "ScriptVariant", "Asset", "MediaJob", "ContentItem",
    "QAReport", "SimilarityReport", "Approval",
    "PublishJob", "PerformanceMetric", "AttributionEvent", "SignalIngestionRun",
    "Experiment", "ExperimentVariant", "WinnerCloneJob",
    "MemoryEntry", "CommentIngestion", "CommentCluster", "CommentCashSignal",
    "KnowledgeGraphNode", "KnowledgeGraphEdge",
    "PortfolioAllocation", "ScaleRecommendation", "CapitalAllocationRecommendation",
    "RevenuLeakReport", "GeoLanguageExpansionRecommendation", "PaidAmplificationJob", "TrustSignalReport",
    "RoadmapRecommendation", "MonetizationRecommendation",
    "OpportunityDecision", "MonetizationDecision", "PublishDecision",
    "SuppressionDecision", "ScaleDecision", "AllocationDecision", "ExpansionDecision",
    "OperatorAlert", "LaunchCandidate", "ScaleBlockerReport",
    "NotificationDelivery", "LaunchReadinessReport", "GrowthCommand", "GrowthCommandRun",
    "SuppressionAction", "AuditLog", "SystemJob", "ProviderUsageCost",
    "PortfolioLaunchPlan", "AccountLaunchBlueprint", "PlatformAllocationReport",
    "NicheDeploymentReport", "GrowthPackBlockerReport", "CapitalDeploymentPlan",
    "CrossAccountCannibalizationReport", "PortfolioOutputReport",
    "OfferLadder", "OwnedAudienceAsset", "OwnedAudienceEvent",
    "MessageSequence", "MessageSequenceStep", "FunnelStageMetric", "FunnelLeakFix",
    "HighTicketOpportunity", "ProductOpportunity", "RevenueDensityReport", "UpsellRecommendation",
    "RecurringRevenueModel", "SponsorInventory", "SponsorPackageRecommendation",
    "TrustConversionReport", "MonetizationMixReport", "PaidPromotionCandidate",
    "LeadOpportunity", "CloserAction", "LeadQualificationReport", "OwnedOfferRecommendation",
    "PricingRecommendation", "BundleRecommendation", "RetentionRecommendation", "ReactivationCampaign",
    "ReferralProgramRecommendation", "CompetitiveGapReport", "SponsorTarget",
    "SponsorOutreachSequence", "ProfitGuardrailReport",
    "ExperimentDecision", "ExperimentOutcome", "ExperimentOutcomeAction",
    "ContributionReport", "AttributionModelRun",
    "CapacityReport", "QueueAllocationDecision",
    "OfferLifecycleReport", "OfferLifecycleEvent",
    "CreativeMemoryAtom", "CreativeMemoryLink",
    "RecoveryIncident", "RecoveryAction",
    "DealDeskRecommendation", "DealDeskEvent",
    "KillLedgerEntry", "KillHindsightReview",
    "AudienceStateReport", "AudienceStateEvent",
    "ReputationReport", "ReputationEvent",
    "MarketTimingReport", "MacroSignalEvent",
    "AutomationExecutionPolicy", "AutomationExecutionRun", "ExecutionBlockerEscalation",
    "SignalScanRun", "NormalizedSignalEvent", "AutoQueueItem",
    "AccountWarmupPlan", "AccountOutputReport", "AccountMaturityReport",
    "PlatformWarmupPolicy", "OutputRampEvent",
    "ExecutionPolicy", "AutonomousRun", "AutonomousRunStep",
    "DistributionPlan", "MonetizationRoute", "SuppressionExecution", "ExecutionFailure",
    "FunnelExecutionRun", "PaidOperatorRun", "PaidOperatorDecision",
    "SponsorAutonomousAction", "RetentionAutomationAction",
    "RecoveryEscalation", "SelfHealingAction",
    "AgentRun", "AgentMessage", "RevenuePressureReport",
    "OverridePolicy", "EscalationEvent", "BlockerDetectionReport", "OperatorCommand",
    "BrainMemoryEntry", "BrainMemoryLink",
    "AccountStateSnapshot", "OpportunityStateSnapshot",
    "ExecutionStateSnapshot", "AudienceStateSnapshotV2",
    "StateTransitionEvent",
    "BrainDecision", "PolicyEvaluation", "ConfidenceReport",
    "UpsideCostEstimate", "ArbitrationReport",
    "AgentRegistryEntry", "AgentRunV2", "AgentMessageV2",
    "WorkflowCoordinationRun", "CoordinationDecision", "SharedContextEvent",
    "MetaMonitoringReport", "SelfCorrectionAction",
    "ReadinessBrainReport", "BrainEscalation",
    "BufferProfile", "BufferPublishJob", "BufferPublishAttempt",
    "BufferStatusSync", "BufferBlocker",
    "AnalyticsImport", "AnalyticsEvent", "ConversionImport", "ConversionEvent",
    "ExperimentObservationImport", "ExperimentLiveResult",
    "CrmContact", "CrmSync", "EmailSendRequest", "SmsSendRequest", "MessagingBlocker",
    "CreatorRevenueOpportunity", "UgcServiceAction", "ServiceConsultingAction",
    "PremiumAccessAction", "LicensingAction", "SyndicationAction", "DataProductAction",
    "MerchAction", "LiveEventAction", "OwnedAffiliateProgramAction",
    "AvenueExecutionTruth",
    "CreatorRevenueBlocker", "CreatorRevenueEvent",
    "WebhookEvent", "ExternalEventIngestion", "SequenceTriggerAction",
    "PaymentConnectorSync", "PlatformAnalyticsSync", "AdReportingImport",
    "BufferExecutionTruth", "BufferExecutionEvent", "BufferRetryRecord", "BufferCapabilityCheck",
    "ProviderRegistryEntry", "ProviderCapability", "ProviderDependency",
    "ProviderReadinessReport", "ProviderUsageEvent", "ProviderBlocker",
    "CopilotChatSession", "CopilotChatMessage", "CopilotResponseCitation",
    "CopilotActionSummary", "CopilotIssueSummary",
    "GatekeeperCompletionReport",
    "GatekeeperTruthReport",
    "GatekeeperExecutionClosureReport",
    "GatekeeperTestReport",
    "GatekeeperDependencyReport",
    "GatekeeperContradictionReport",
    "GatekeeperOperatorCommandReport",
    "GatekeeperExpansionPermission",
    "GatekeeperAlert",
    "GatekeeperAuditLedger",
    "AccountExpansionAdvisory",
    "ContentFormRecommendation",
    "ContentFormMixReport",
    "ContentFormBlocker",
    "ContentRoutingDecision",
    "ContentRoutingCostReport",
    "WinningPatternMemory",
    "WinningPatternEvidence",
    "WinningPatternCluster",
    "LosingPatternMemory",
    "PatternReuseRecommendation",
    "PatternDecayReport",
    "ActiveExperiment",
    "PWExperimentVariant",
    "PWExperimentAssignment",
    "PWExperimentObservation",
    "PWExperimentWinner",
    "PWExperimentLoser",
    "PromotedWinnerRule",
    "CapitalAllocationReport",
    "AllocationTarget",
    "CAAllocationDecision",
    "CAAllocationConstraint",
    "CAAllocationRebalance",
    "AccountStateReport",
    "AccountStateTransition",
    "AccountStateAction",
    "QualityGovernorReport",
    "QualityDimensionScore",
    "QualityBlock",
    "QualityImprovementAction",
    "ObjectionSignal",
    "ObjectionCluster",
    "ObjectionResponse",
    "ObjectionPriorityReport",
    "OpportunityCostReport",
    "RankedAction",
    "CostOfDelayModel",
    "FailureFamilyReport",
    "FailureFamilyMember",
    "SuppressionRule",
    "SuppressionEvent",
    "LandingPage", "LandingPageVariant", "LandingPageBlock", "LandingPageQualityReport", "LandingPagePublishRecord",
    "Campaign", "CampaignVariant", "CampaignAsset", "CampaignDestination", "CampaignBlocker",
    "AffiliateNetworkAccount", "AffiliateMerchant", "AffiliateOffer", "AffiliateLink",
    "AffiliateClickEvent", "AffiliateConversionEvent", "AffiliateCommissionEvent", "AffiliatePayoutEvent",
    "AffiliateBlocker", "AffiliateDisclosure", "AffiliateLeak",
    "BrandGovernanceProfile", "BrandVoiceRule", "BrandKnowledgeBase", "BrandKnowledgeDocument",
    "BrandAudienceProfile", "BrandEditorialRule", "BrandAssetLibrary", "BrandStyleToken",
    "BrandGovernanceViolation", "BrandGovernanceApproval",
    "EnterpriseRole", "EnterprisePermission", "EnterpriseUserGroup", "EnterpriseAccessScope",
    "AuditTrailEvent", "SensitiveDataPolicy", "ModelIsolationPolicy",
    "ComplianceControlReport", "RiskOverrideEvent",
    "WorkflowDefinition", "WorkflowStep", "WorkflowAssignment", "WorkflowInstance",
    "WorkflowInstanceStep", "WorkflowApproval", "WorkflowRejection", "WorkflowOverride", "WorkflowTemplate",
    "ExecutionCapacityReport", "ExecutionQueueSegment", "WorkloadAllocation", "ThroughputEvent",
    "BurstEvent", "UsageCeilingRule", "DegradationEvent", "ScaleHealthReport",
    "EnterpriseConnector", "EnterpriseConnectorSync", "SocialListeningEvent", "CompetitorSignalEvent",
    "InternalBusinessSignal", "ListeningCluster", "SignalResponseRecommendation", "IntegrationBlocker",
    "ExecutiveKPIReport", "ExecutiveForecast", "UsageCostReport", "ProviderUptimeReport",
    "OversightModeReport", "ServiceHealthReport", "ExecutiveAlert",
    "AffiliateGovernanceRule", "AffiliateBannedEntity", "AffiliateApproval",
    "AffiliateAuditEvent", "AffiliateRiskFlag", "OwnedAffiliatePartner", "OwnedPartnerConversion",
    "OfferLabOffer", "OfferLabVariant", "OfferLabPricingTest", "OfferLabPositioningTest",
    "OfferLabBundle", "OfferLabUpsell", "OfferLabDownsell", "OfferLabCrossSell",
    "OfferLabBlocker", "OfferLabLearning",
    "RevenueLeakReport", "RevenueLeakEvent", "LeakCluster", "LeakCorrectionAction", "RevenueLossEstimate",
    "SimulationRun", "SimulationScenario", "SimulationAssumption", "SimulationOutcome", "SimulationRecommendation",
    "RecoveryIncidentV2", "RollbackAction", "RerouteAction", "ThrottlingAction", "RecoveryOutcome", "RecoveryPlaybook",
    "OperatorPermissionMatrix", "AutonomyActionPolicy", "ActionApprovalRequirement", "ActionOverrideRule", "ActionExecutionMode",
    "CausalAttributionReport", "CausalSignal", "CausalHypothesis", "CausalConfidenceReport", "CausalCreditAllocation",
    "TrendSignalEvent", "TrendVelocityReport", "ViralOpportunity", "TrendOpportunityScore",
    "TrendDuplicate", "TrendSuppressionRule", "TrendBlocker", "TrendSourceHealth",
    "NicheScore", "AccountWarmupPlan", "FleetStatusReport", "AccountVoiceProfile",
    "ContentRepurposeRecord", "CompetitorAccount", "DailyIntelligenceReport",
    "AIPersonality", "PersonalityMemory", "PersonalityEvolution",
    "StudioProject", "StudioScene", "CharacterBible", "StylePreset",
    "StudioGeneration", "StudioActivity",
]
