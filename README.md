graph TD
    %% Styling Definitions
    classDef user fill:#eef2ff,stroke:#6366f1,stroke-width:2px,color:#3730a3
    classDef frontend fill:#eff6ff,stroke:#3b82f6,stroke-width:1px,color:#1e3a8a
    classDef backend fill:#f0fdf4,stroke:#22c55e,stroke-width:1px,color:#14532d
    classDef engine fill:#fff7ed,stroke:#f97316,stroke-width:1px,color:#9a3412
    classDef report fill:#fef2f2,stroke:#ef4444,stroke-width:1px,color:#991b1b
    classDef database fill:#f0fdf4,stroke:#22c55e,stroke-width:1px,color:#14532d

    %% User Node
    C((Clinician)):::user

    %% 1. Clinical Workflow (Frontend)
    subgraph Clinical Workflow
        CW["Clinical Workstation<br/>[page.js]"]:::frontend
        CR["Clinical Review<br/>[page.js]"]:::frontend
        RR["Risk Review<br/>[page.js]"]:::frontend
        AS["Assessment Selection<br/>[page.js]"]:::frontend
        PI["Patient Intake<br/>[page.js]"]:::frontend
        
        CW -- reviews risk --> RR
        CW -- selects --> AS
        CW -- starts with --> PI
    end

    C -- uses --> CW

    %% 2. Backend Services
    subgraph Backend Services
        FS["FastAPI Service<br/>[api.py]"]:::backend
        AUTH["Authentication<br/>[api.py]"]:::backend
        AR[("Assessment Records<br/>[api.py]")]:::database
        AL["Audit Logging<br/>[api.py]"]:::backend
        HS["History & Statistics<br/>[api.py]"]:::backend
        
        FS -- checks access --> AUTH
        FS -- reads and writes --> AR
        FS -- records actions --> AL
        FS -- serves queries --> HS
    end

    %% Frontend to Backend Connections
    CW -. requests analysis .-> FS
    FS -. accepts review .-> CR

    %% 3. Diagnostic Analysis
    subgraph Diagnostic Analysis
        XX["X-ray Explainability<br/>[xray_engine.py]"]:::engine
        DP["DICOM Processing<br/>[dicom_handler.py]"]:::engine
        CX["Chest X-ray<br/>[api.py]"]:::engine
        EE["ECG Explainability<br/>[ecg_engine.py]"]:::engine
        FA["Fracture Analysis<br/>[api.py]"]:::engine
        EA["ECG Analysis<br/>[api.py]"]:::engine
        
        FS -- routes --> DP
        FS -- routes --> CX
        FS -- routes --> FA
        FS -- routes --> EA
        FS -- routes --> XX
        FS -- routes --> EE
    end

    %% 4. Transparency & Reporting
    subgraph Transparency & Reporting
        MT["Model Transparency<br/>[page.js]"]:::report
        CE["Clinical Explanations<br/>[page.js]"]:::report
        SPR["Signed PDF Reports<br/>[page.js]"]:::report
    end

    %% Final Connections
    CW -- shows metrics --> MT
    CW -- shows attribution --> CE
    CW -- exports report --> SPR
    
    XX -. produces Grad-CAM .-> CE
    EE -. produces saliency .-> CE