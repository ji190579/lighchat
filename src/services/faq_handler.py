# faq_handler.py
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
import os
from datetime import datetime

class FAQHandler:
    def __init__(self):
        # ✅ Your correct local model path
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        
        print("Loading sentence transformer model...")
        try:
            self.model = SentenceTransformer(model_name)
            print("✅ Model loaded successfully")
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            raise
        # self.faqs = "data/faq.py"  # Load FAQs from py file
        
        # ✅ FAQ Database
        self.faqs = [
            # ============================================================
            # PERSONAL INFORMATION & EDUCATION
            # ============================================================
            {
                "question": "Where are you from?",
                "answer": "I'm from Beirut, Lebanon, and I've built my career in banking technology serving regional and international financial institutions."
            },
            {
                "question": "Which university did you attend?",
                "answer": "I earned my Bachelor's degree in Business Computer from the Lebanese University."
            },
            {
                "question": "What did you study?",
                "answer": "I studied Business Computer, combining software engineering, databases, and business systems."
            },
            {
                "question": "When did you graduate?",
                "answer": "I graduated in 2003 with a Bachelor's degree in Business Computer."
            },
            {
                "question": "What languages do you speak?",
                "answer": "I speak Arabic, French, and English."
            },
            
            # ============================================================
            # CAREER OVERVIEW
            # ============================================================
            {
                "question": "What is your background?",
                "answer": "I'm a Principal Software Engineer with over 20 years of experience specializing in core banking, trade finance systems, and enterprise modernization."
            },
            {
                "question": "How many years of experience do you have?",
                "answer": "I have more than 18 years of experience in software engineering within the banking sector."
            },
            {
                "question": "What is your current role?",
                "answer": "I'm currently a Principal Software Engineer leading modernization and microservices transformation initiatives."
            },
            {
                "question": "Which companies have you worked for?",
                "answer": "I worked at Path Solutions from 2006 until 2021, and currently at Azentio."
            },
            {
                "question": "Tell me about your career journey",
                "answer": "I started with PowerBuilder client-server systems, transitioned to Java web applications, evolved into microservices architecture, and now integrate AI solutions into banking systems."
            },
            
            # ============================================================
            # JAVA & ENTERPRISE EXPERIENCE
            # ============================================================
            {
                "question": "What is your Java experience?",
                "answer": "I have 10+ years of experience with Java/JEE building enterprise banking applications using Spring Boot, Struts2, and microservices architecture."
            },
            {
                "question": "Do you know Spring Boot?",
                "answer": "Yes, I use Spring Boot extensively for building RESTful microservices and scalable enterprise applications."
            },
            {
                "question": "What frameworks do you use?",
                "answer": "I work with Spring Boot, Struts2, MyBatis3, JSP/Servlets, and modern microservices tooling."
            },
            {
                "question": "Have you built enterprise systems?",
                "answer": "Yes, I've built and maintained enterprise-scale core banking systems handling high transaction volumes and regulatory compliance."
            },
            
            # ============================================================
            # POWERBUILDER & MIGRATION
            # ============================================================
            {
                "question": "Do you have PowerBuilder experience?",
                "answer": "Yes, I worked more than 10 years with PowerBuilder developing core banking client-server systems."
            },
            {
                "question": "Have you migrated legacy systems?",
                "answer": "Yes, I led migration projects from PowerBuilder to Java web applications while preserving business logic and ensuring financial consistency."
            },
            {
                "question": "How do you approach legacy modernization?",
                "answer": "I analyze embedded business rules, extract domain logic, redesign using layered architecture, and validate using real banking scenarios."
            },
            
            # ============================================================
            # TRADE FINANCE DOMAIN
            # ============================================================
            {
                "question": "What trade finance systems have you worked on?",
                "answer": "I've worked on Letters of Credit, Bank Guarantees, Bills for Collection, amendments, settlements, and SWIFT integration."
            },
            {
                "question": "What is a Letter of Credit?",
                "answer": "A Letter of Credit is a bank guarantee ensuring payment to a seller upon compliant document presentation. I've implemented full LC lifecycle processing."
            },
            {
                "question": "Have you worked with SWIFT?",
                "answer": "Yes, I've handled SWIFT MT103 and MT202 messages and participated in ISO 20022 migration projects."
            },
            {
                "question": "What is ISO 20022?",
                "answer": "ISO 20022 is a modern global financial messaging standard replacing legacy SWIFT MT formats with structured XML-based messages."
            },
            
            # ============================================================
            # MICROSERVICES & ARCHITECTURE
            # ============================================================
            {
                "question": "What is your microservices experience?",
                "answer": "I design and implement microservices using Spring Boot, Eureka, API Gateway, Kafka, and distributed tracing tools."
            },
            {
                "question": "Have you used Kafka?",
                "answer": "Yes, I use Kafka for event-driven communication between banking microservices ensuring reliable message delivery."
            },
            {
                "question": "Do you use API Gateway?",
                "answer": "Yes, I implement API Gateway for routing, authentication, load balancing, and rate limiting."
            },
            {
                "question": "How do you ensure transaction consistency?",
                "answer": "I apply Saga patterns, idempotent APIs, and careful rollback strategies instead of traditional distributed transactions."
            },
            
            # ============================================================
            # DATABASE EXPERIENCE
            # ============================================================
            {
                "question": "What databases do you know?",
                "answer": "I have extensive experience with Oracle, Sybase, and PostgreSQL in high-volume banking systems."
            },
            {
                "question": "Do you know PL/SQL?",
                "answer": "Yes, I have deep expertise in PL/SQL including stored procedures, packages, triggers, and performance optimization."
            },
            {
                "question": "How do you optimize databases?",
                "answer": "Through indexing strategies, query tuning, partitioning, and minimizing locking contention."
            },
            
            # ============================================================
            # DEVOPS & CONTAINERS
            # ============================================================
            {
                "question": "Do you use Docker?",
                "answer": "Yes, I containerize banking microservices using Docker and Podman for consistent deployment."
            },
            {
                "question": "What is Podman?",
                "answer": "Podman is a daemonless container engine used as a secure alternative to Docker in enterprise environments."
            },
            
            # ============================================================
            # AI & MACHINE LEARNING
            # ============================================================
            {
                "question": "What AI projects have you built?",
                "answer": "I've built RAG systems, LLM-based chatbots, semantic search solutions, and AI-powered document analysis tools."
            },
            {
                "question": "What is RAG?",
                "answer": "RAG (Retrieval-Augmented Generation) combines vector search retrieval with large language models to produce grounded, context-aware responses."
            },
            {
                "question": "Have you worked with LLMs?",
                "answer": "Yes, I've worked with GPT, Claude, and open-source LLMs to build intelligent enterprise chatbots."
            },
            {
                "question": "Do you know embeddings?",
                "answer": "Yes, I use embeddings to perform semantic similarity search and document retrieval in AI systems."
            },
            
            # ============================================================
            # FINE-TUNING & MODEL TRAINING
            # ============================================================
            {
                "question": "What is supervised fine-tuning?",
                "answer": "Supervised fine-tuning trains a pretrained model on structured input-output pairs to specialize it for a domain."
            },
            {
                "question": "What is LoRA?",
                "answer": "LoRA is a parameter-efficient fine-tuning technique that adapts models by training small low-rank matrices instead of the full model."
            },
            {
                "question": "When should you fine-tune instead of using RAG?",
                "answer": "Fine-tuning is better for shaping behavior and reasoning style, while RAG is better for grounding responses in frequently changing knowledge."
            },
            
            # ============================================================
            # FRONTEND & REACT
            # ============================================================
            {
                "question": "Do you know React?",
                "answer": "Yes, I'm currently learning React to build modern, responsive user interfaces with components, hooks, and state management."
            },
            {
                "question": "What frontend technologies do you use?",
                "answer": "I have experience with HTML/CSS, JavaScript, JSP templates, and I'm currently expanding my skills in React and Tailwind CSS."
            },
            
            # ============================================================
            # PYTHON
            # ============================================================
            {
                "question": "Do you know Python?",
                "answer": "Yes, I use Python for AI/ML projects, data processing, automation scripts, and building APIs with FastAPI."
            },
            {
                "question": "Have you used FastAPI?",
                "answer": "Yes, I build RESTful APIs with FastAPI for AI services, chatbots, and microservices due to its speed and type safety."
            },
            
            # ============================================================
            # AUTHENTICATION & SECURITY
            # ============================================================
            {
                "question": "Do you know Keycloak?",
                "answer": "Yes, I use Keycloak for identity and access management, implementing OAuth2, OpenID Connect, and SSO for banking applications."
            },
            {
                "question": "Have you worked with OAuth?",
                "answer": "Yes, I've implemented OAuth2 authentication flows for secure API access, integrating with identity providers like Keycloak."
            },
            
            # ============================================================
            # FUTURE & VISION
            # ============================================================
            {
                "question": "Why are you learning AI?",
                "answer": "AI represents the next transformation wave in enterprise banking systems, and I'm integrating it with my domain expertise."
            },
            {
                "question": "What are your career goals?",
                "answer": "My goal is to bridge traditional banking systems with modern AI-driven architectures and intelligent automation."
            },
        ]
        
        print(f"Encoding {len(self.faqs)} FAQ questions...")
        self.faq_questions = [faq["question"] for faq in self.faqs]
        self.faq_embeddings = self.model.encode(self.faq_questions)
        print(f"✅ {len(self.faqs)} FAQ embeddings ready")
    
    def find_answer(self, user_question, threshold=0.65):
        """
        Find best matching FAQ
        
        Args:
            user_question: User's input
            threshold: Minimum similarity score (0-1)
        
        Returns:
            dict with answer, score, matched_question, source
        """
        try:
            user_embedding = self.model.encode([user_question])
            similarities = cosine_similarity(user_embedding, self.faq_embeddings)[0]
            
            # Get top 3 matches
            top_3_indices = similarities.argsort()[-3:][::-1]
            top_3_matches = [
                {
                    "question": self.faq_questions[i],
                    "score": float(similarities[i])
                }
                for i in top_3_indices
            ]
            
            best_idx = similarities.argmax()
            best_score = float(similarities[best_idx])
            
            # Log query
            self._log_query(user_question, top_3_matches, threshold)
            
            if best_score >= threshold:
                print(f"✅ FAQ HIT: '{self.faq_questions[best_idx]}' ({best_score:.2%})")
                return {
                    "answer": self.faqs[best_idx]["answer"],
                    "score": best_score,
                    "matched_question": self.faq_questions[best_idx],
                    "source": "FAQ",
                    "top_3": top_3_matches
                }
            else:
                print(f"❌ No FAQ match. Best: '{self.faq_questions[best_idx]}' ({best_score:.2%})")
                return {
                    "answer": None,
                    "score": best_score,
                    "matched_question": self.faq_questions[best_idx],
                    "source": "NO_MATCH",
                    "top_3": top_3_matches
                }
        
        except Exception as e:
            print(f"❌ Error in find_answer: {e}")
            return {
                "answer": None,
                "score": 0.0,
                "source": "ERROR"
            }
    
    def _log_query(self, user_question, top_3_matches, threshold):
        """Log all FAQ queries for analysis"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_question": user_question,
            "top_3_matches": top_3_matches,
            "threshold": threshold,
            "hit": top_3_matches[0]["score"] >= threshold
        }
        
        os.makedirs("logs", exist_ok=True)
        with open("logs/faq_queries.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ✅ Test the handler
if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing FAQ Handler")
    print("="*60)
    
    handler = FAQHandler()
    
    test_questions = [
        "What's your Java experience?",
        "Tell me about PowerBuilder",
        "Do you know Docker?",
        "What AI projects have you done?",
        "Where are you from?",
        "What's the weather like today?"  # Should not match
    ]
    
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = handler.find_answer(q, threshold=0.65)
        if result["answer"]:
            print(f"✅ A: {result['answer'][:100]}...")
            print(f"   Score: {result['score']:.2%}")
        else:
            print(f"❌ No match (score: {result['score']:.2%})")