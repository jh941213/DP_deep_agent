# UCP Checkout Process & Fallback Workflow

This document visualizes the checkout creation process, including the **Authentication Fallback Mechanism** implemented for stores with strict UCP security (e.g., Monos, Kith).

```mermaid
sequenceDiagram
    actor User
    participant Agent
    participant UCP_Tool as ucp_create_checkout (Tool)
    participant StoreAP as Store UCP Endpoint
    participant Fallback as Fallback Logic

    User->>Agent: "Create checkout for Monos Metro Sling"
    Agent->>UCP_Tool: Call with line_items & store_url
    
    rect rgb(240, 248, 255)
        note right of UCP_Tool: 1. Attempt Standard UCP Checkout
        UCP_Tool->>StoreAPI: POST /create_checkout (RPC)
        
        alt Authentication Success
            StoreAPI-->>UCP_Tool: { result: "checkout_json" }
            UCP_Tool-->>Agent: Return Checkout Object
            Agent-->>User: Show UCP Checkout Card
        else Authentication Failed (Error -32000)
            StoreAPI-->>UCP_Tool: { error: "AuthenticationFailed" }
            
            rect rgb(255, 240, 240)
                note right of UCP_Tool: 2. Fallback Mechanism Triggered
                UCP_Tool->>Fallback: Parse line_items_json
                Fallback->>Fallback: Extract Variant IDs
                Fallback->>Fallback: Construct Cart Permalink
                note right of Fallback: https://store.com/cart/{vid}:{qty}
                Fallback-->>UCP_Tool: Return Fallback Object (Mock UCP format)
            end
            
            UCP_Tool-->>Agent: Return Fallback Checkout Object
            Agent-->>User: Show Checkout Card (Direct Link)
        end
    end
```

## Key Logic

1.  **Primary Strategy**: Attempt to use the standardized Google UCP `create_checkout` method.
2.  **Error Handling**: specifically listen for `AuthenticationFailed` or `Unsupported authentication strategy`.
3.  **Fallback Strategy**: 
    - Parse the intended items.
    - Generate a **Shopify Cart Permalink** (Standard Feature).
    - Wrap the URL in a structure compatible with the Agent's frontend, ensuring the UI renders correctly without breaking the user experience.
