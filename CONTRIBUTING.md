# Contributing to DreaMMO

Thank you for your interest in contributing to **DreaMMO** - an open-source text-based MMORPG!

## Welcome Contributors! 🎮

We're looking for:
- 🐍 **Python/FastAPI developers** - Backend & game mechanics
- ⚛️ **React/JavaScript developers** - Frontend & UI
- 🎨 **Game designers** - Mechanics, balance, content
- 📝 **Technical writers** - Documentation
- 🐛 **QA testers** - Bug reports and testing
- 🎵 **Audio designers** - Sound effects and narration

---

## Getting Started

### 1. Fork & Clone
```bash
git clone https://github.com/YOUR_USERNAME/DreaMMO.git
cd DreaMMO
```

### 2. Create Feature Branch
```bash
git checkout -develop develop
git checkout -b feature/your-feature-name
```

*Branch naming convention:*
- `feature/` - New feature
- `fix/` - Bug fix
- `docs/` - Documentation
- `refactor/` - Code refactoring
- `test/` - Tests

### 3. Setup Development Environment
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 4. Make Changes
- Create focused, atomic commits
- Write descriptive commit messages
- Add tests for new features
- Update documentation

### 5. Test Your Changes
```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run lint
npm run build
```

### 6. Push & Create Pull Request
```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear description of changes
- Reference to related issues (#123)
- Screenshots for UI changes
- Test results

---

## Code Style Guide

### Python (Backend)
```python
# Use Black formatter
black backend/

# Use PEP 8 style
# - Max line length: 100
# - Use type hints
# - Add docstrings

def calculate_damage(attacker_stats: dict, defender_stats: dict) -> int:
    """
    Calculate damage dealt in combat.
    
    Args:
        attacker_stats: Dictionary with player stats
        defender_stats: Dictionary with opponent stats
        
    Returns:
        Damage value as integer
    """
    base_damage = attacker_stats.get('strength', 10)
    armor = defender_stats.get('armor', 0)
    return max(1, base_damage - armor)
```

### JavaScript/React (Frontend)
```jsx
// Use functional components
// Use React hooks
// Add prop types or TypeScript

import React, { useState } from 'react';

function CombatComponent({ characterId }) {
  const [damage, setDamage] = useState(0);
  
  return (
    <div>
      <h3>Combat</h3>
      <p>Damage: {damage}</p>
    </div>
  );
}

export default CombatComponent;
```

---

## Commit Message Format

```
feat(combat): implement hit chance calculation

- Added dexterity modifier to hit calculation
- Added weapon skill multiplier
- Fixed armor calculation bug

Closes #123
```

Format:
- `type(scope): description`
- Blank line
- Detailed explanation (optional)
- Reference issues with `Closes #123`

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

---

## Pull Request Process

1. **Before submitting:**
   - [ ] Code compiles without errors
   - [ ] All tests pass
   - [ ] No console warnings
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated

2. **PR Description should include:**
   - What does this PR do?
   - How to test the changes?
   - Any breaking changes?
   - Screenshots for UI changes

3. **Review process:**
   - At least 1 maintainer review required
   - Address reviewer comments
   - Re-request review after changes

4. **Merge:**
   - Squash commits if requested
   - Delete feature branch
   - Celebrate! 🎉

---

## Feature Development Guide

### Adding a New Combat Mechanic

**Example: "Block" mechanic**

1. **Plan**: Create GitHub issue
   - Describe the feature
   - Add acceptance criteria
   - Estimate effort

2. **Database** (if needed):
   - Update `backend/database/schema.sql`
   - Add new tables/columns
   - Create migration

3. **Backend**:
   ```python
   # Add to backend/routes.py
   @router.post("/combat/block")
   async def block_attack(defender_id: int):
       """Defender attempts to block attack"""
       # Implementation here
       return {"status": "blocked"}
   ```

4. **Frontend**:
   ```jsx
   // Create frontend/src/components/BlockButton.jsx
   function BlockButton({ onBlock }) {
     return <button onClick={onBlock}>Block</button>;
   }
   ```

5. **Test**:
   - Write unit tests
   - Manual testing
   - Test edge cases

6. **Document**:
   - Update DEVELOPMENT.md
   - Add code comments
   - Update API docs

7. **Submit PR**:
   - Link to GitHub issue
   - Describe changes clearly
   - Request review

---

## Testing

### Backend Tests
```bash
cd backend

# Run all tests
pytest

# Run specific test
pytest tests/test_combat.py::test_damage_calculation

# With coverage
pytest --cov=. --cov-report=html
```

### Frontend Tests
```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm test -- --coverage
```

### Manual Testing Checklist
- [ ] Test on desktop browser
- [ ] Test on mobile browser
- [ ] Test on Firefox, Chrome, Safari
- [ ] Test game mechanics end-to-end
- [ ] Check error handling
- [ ] Verify database data

---

## Documentation

### Keep Updated:
- README.md - Project overview
- SETUP.md - Installation
- DEVELOPMENT.md - Developer guide
- API endpoints in code docstrings
- Database schema comments

### Add New Docs For:
- New features
- Complex mechanics
- API changes
- Setup changes
- Game balance notes

Example:
```markdown
## New Feature: Block Mechanic

Defender can block incoming attacks based on:
- Shield equipped (doubles block chance)
- Dexterity stat (primary modifier)
- Fatigue level (decreases effectiveness)

Block success: 50% + (dexterity * 2) - fatigue

See implementation in routes.py::block_attack()
```

---

## Issues & Discussions

### Reporting Bugs
1. Check if already reported
2. Use bug report template
3. Include:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Screenshots/logs
   - Environment details

### Suggesting Features
1. Check existing issues
2. Use feature request template
3. Explain:
   - User problem it solves
   - Proposed solution
   - Alternative solutions
   - Additional context

### Discussions
- Game mechanics
- Balance ideas
- Architecture discussions
- Community questions

---

## Code Review Guidelines

### As a Reviewer:
- Be respectful and constructive
- Ask questions instead of making demands
- Approve when satisfied
- Request changes if needed

### As a Contributor:
- Respond to feedback promptly
- Ask for clarification if needed
- Don't take criticism personally
- Update code and request re-review

---

## Project Structure for New Contributors

```
backend/
├── main.py           ← Start here for API structure
├── routes.py         ← Add new endpoints here
├── config.py         ← Configuration handling
└── database/
    ├── connection.py ← DB utilities
    └── schema.sql    ← Database schema

frontend/
├── src/
│   ├── App.jsx       ← Main component
│   └── components/   ← Add components here
└── vite.config.js    ← Build config
```

---

## Help & Questions

- 📖 Read [DEVELOPMENT.md](DEVELOPMENT.md)
- 💬 Open a discussion
- 🐛 Check existing issues
- 📧 Email maintainers

---

## Code of Conduct

- Be respectful and inclusive
- Welcome all skill levels
- Focus on the code, not the person
- Help each other learn and grow
- Report harassment to maintainers

---

## Licensing

By contributing, you agree that your contributions are licensed under the MIT License.

---

## Recognition

All contributors are recognized in:
- README.md - Contributors section
- GitHub - Contribution graph
- Release notes - Changelog

Thank you for contributing to DreaMMO! 🎮❤️

---

## Quick Reference

```bash
# Setup
git clone https://github.com/YOUR_USERNAME/DreaMMO.git
cd DreaMMO
git checkout -b feature/amazing-feature

# Development
cd backend && venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload

# cd frontend
npm run dev

# Testing
pytest  # Backend
npm test # Frontend

# Commit
git add .
git commit -m "feat(module): description"
git push origin feature/amazing-feature

# Create Pull Request on GitHub!
```

---

Happy coding! 🚀🎮
