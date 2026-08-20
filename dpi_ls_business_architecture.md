# DPI-LS: Business Architecture Workflow

This document outlines the end-to-end business architecture and event-driven workflow for the **Digital Performance Index for Life Sciences (DPI-LS)** system.

```mermaid
flowchart TD
    %% Define Global Styles
    classDef primary fill:#0033A0,stroke:#002277,stroke-width:3px,color:#ffffff,font-weight:bold,rx:10px,ry:10px;
    classDef secondary fill:#007BFF,stroke:#0056b3,stroke-width:2px,color:#ffffff,rx:8px,ry:8px;
    classDef database fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#000000;
    classDef dashboard fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#000000;
    classDef userAction fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#000000,stroke-dasharray: 5 5;
    classDef security fill:#FF5722,stroke:#BF360C,stroke-width:3px,color:#ffffff,font-weight:bold,rx:10px,ry:10px;
    
    %% Main Nodes
    subgraph Phase 0: Security [Phase 0: Authentication & RBAC]
        direction TB
        L([0a. User Login]):::security
        R{0b. RBAC Verification<br/>Admin/Manager/Customer}:::security
    end

    subgraph Phase 1: Preparation [Phase 1: Agent & Data Configuration]
        direction TB
        A([1. Agent Onboarding]):::primary
        B([2. KRA Configuration]):::primary
        C([3. Static Data Config]):::primary
    end

    subgraph Phase 2: Evaluation [Phase 2: Human & Machine Evaluation]
        direction TB
        D([4. Manager Review]):::userAction
        E{5. Event-Driven<br/>Telemetry Trigger}:::secondary
        F[(Database<br/>Aggregation & Engine)]:::database
    end
    
    subgraph Phase 3: Visibility [Phase 3: Executive Visibility]
        direction TB
        G[[6. DPI-LS Live Dashboard]]:::dashboard
        G1(Main Leaderboard)
        G2(Resources Hub)
        G3(Score Analytics)
        G4(Feedback Portal)
        G5(Agent Profile View)
    end
    
    subgraph Phase 4: Termination [Phase 4: Session End]
        direction TB
        H([7. Logout Session]):::security
        L2([8. Return to Login]):::security
    end

    %% Connections
    L -->|Validates JWT Credentials| R
    R -->|Authorizes Specific Roles| A
    
    A -->|Registers Identity & Ownership| B
    B -->|Defines Target Metrics| C
    C -->|Sets Human Baselines| D
    
    D -->|Submits SME Rating 1 to 5| E
    E -->|Background Execution| F
    F -->|Calculates 7 Dimensions| G
    
    G --- G1
    G --- G2
    G --- G3
    G --- G4
    G --- G5
    
    G4 -->|Auto-Redirect on Submit| G5
    G1 -->|Click Agent Name| G5
    
    G -->|Click Logout| H
    G5 -->|Click Logout| H
    H -->|Clears JWT Token| L2
```

## Workflow Phases

### Phase 0: Secure Login
First, users log into the system securely. The platform checks their role to see if they are an Admin, Manager, or Customer. This ensures that only authorized people can add new agents, rate their own agents, or submit feedback, keeping the entire system safe and accountable.

### Phase 1: Agent Onboarding
Once logged in, an Admin registers a new AI Digital Worker into the system. This step is crucial because it assigns real human owners (a Business Owner, Technical Owner, and Manager) to the AI, ensuring it never operates in the dark without human supervision.

### Phase 2: Setting Goals
Next, the Admin defines the specific goals (Key Result Areas) the AI needs to achieve. By setting target metrics and weighing their importance, the system learns exactly what success looks like for that specific business process.

### Phase 3: Adding Human Benchmarks
The system then brings in real-world data, like how much a human costs or how fast a human works. By having this baseline, the platform can mathematically prove if the AI is actually saving time and money compared to a human worker.

### Phase 4: Manager Approval
After the AI has been running, its assigned human manager logs in to rate its performance on a scale of 1 to 5 and leaves comments. This ensures that cold, hard data is always balanced with real human feedback.

### Phase 5: The Automated Engine
The moment the manager submits their review, it triggers the backend engine. Without anyone having to click another button, the system automatically gathers all the metrics, runs deep evaluations across our monitoring tools, and computes the final score in the background.

### Phase 6: The Executive Dashboard
Finally, all these calculations are pushed to a live, easy-to-read web dashboard. Here, executives can view a leaderboard ranking all their AI agents. From the dashboard, they can click on any agent to open its detailed profile, read documentation in the resources hub, or drill down into how the metrics were calculated. End-users can also submit direct feedback, which automatically updates the agent's profile and drives continuous improvement.

### Phase 7: Secure Logout (Session Termination)
When a user finishes their tasks on the Dashboard or Agent Profile, they can securely click **Logout**. This destroys their session token and returns them safely to the login screen, completing the full lifecycle and keeping the platform secure.
